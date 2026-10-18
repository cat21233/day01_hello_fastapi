"""数据库连接层 —— engine / Session 工厂 / Base / get_db 依赖 / 建表 / 种子数据。

为什么单独一个文件？
    routers 只该知道「怎么用 session」，不该知道「怎么连库」。
    本地 SQLite → 真实 MySQL，只改 .env 里的 DATABASE_URL，路由层一个字不用动。

本文件的四样东西，对应四个问题：
    engine       —— 连哪个库？整个进程只建一次（连接池挂在它身上）
    SessionLocal —— 每次请求怎么拿到一个「工作单元」？
    Base         —— 模型类继承谁？谁记得「一共有哪些表」？
    get_db       —— 请求结束时谁负责关掉？FastAPI 依赖
"""

from collections.abc import Generator

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings

# ── 1. Engine：连接池 + 数据库方言 ──────────────────────────────────
# 整个进程只建一次：它内部持有一个连接池，每次开 session 从这里借一条连接。
# 注意：create_engine 只是「准备好参数」，此刻还不会真的连库 ——
# 第一次执行 SQL（或 pool_pre_ping 探活）时才真正握手。
_is_sqlite = settings.database_url.startswith("sqlite")
_is_mysql = settings.database_url.startswith("mysql")

_connect_args: dict = {}
if _is_sqlite:
    # SQLite 特有开关。它默认禁止「一个连接跨线程使用」，
    # 但 FastAPI 会把 def 路由丢进线程池，不同请求可能落在不同线程上，
    # 不关掉就会报：SQLite objects created in a thread can only be used
    # in that same thread。
    _connect_args["check_same_thread"] = False

_engine_kwargs: dict = {
    "connect_args": _connect_args,
    # 连接被数据库单方面掐断（MySQL 默认 wait_timeout = 8 小时）后，
    # 池里那条连接已经是死的。pool_pre_ping 在借出前先 ping 一下，
    # 死了就换一条新的 —— 否则报 MySQL server has gone away。
    "pool_pre_ping": True,
    # True 时把所有 SQL 打到日志里，调试「为什么查出来是空的」神器，
    # 平时关掉（.env 里 DATABASE_ECHO=true 打开）
    "echo": settings.database_echo,
}

if _is_mysql:
    _engine_kwargs.update(
        # 池子里常驻 5 条、忙时最多再临时开 10 条。
        # 总并发别超过 MySQL 的 max_connections（本机 my.ini 写的是 100），
        # 多个 worker 时按 worker 数乘着算。
        pool_size=5,
        max_overflow=10,
        # 连接最多活 1 小时就回收重建，比 MySQL 的 wait_timeout 短，
        # 让「死连接」在我的池子里先被淘汰，而不是等它自己断。
        pool_recycle=3600,
    )

engine = create_engine(settings.database_url, **_engine_kwargs)

# ── 2. SessionLocal：Session 工厂（注意：它本身不是 Session）────────
# 每来一个请求，用工厂现造一个 Session。
#   autoflush=False        免得你还没 commit，一次普通查询就顺手把脏数据 flush 出去
#   expire_on_commit=False commit 之后对象属性仍可读（默认 True 会把对象标成「过期」，
#                          再读属性要补一条 SELECT —— 而那时 session 可能已关闭）
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# ── 3. Base：所有模型类的父类 ───────────────────────────────────────
# 它内部维护一张「类 → 表」的注册表（Base.metadata）。
# create_all 就是遍历这张注册表建表 —— 所以模型必须先被 import 过，才有表可建。
class Base(DeclarativeBase):
    pass


# ── 4. get_db：FastAPI 依赖，管 Session 的生死 ──────────────────────
# yield 之前 = 请求进来（造 Session）
# yield 之后 = 请求结束（关 Session）
# 必须 try/finally：路由里抛异常时也要关，否则连接一直被占，
# 池子占干之后所有请求一起卡死。
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── 5. 建表入口（仅开发期使用）──────────────────────────────────────
# create_all 只建「还不存在的表」，已存     的表一个字都不改。
# → 加字段 / 改字段它管不了，生产要靠 Alembic 迁移（面试高频追问）。
# bind 参数是为了测试能传一个内存 SQLite 的 engine 进来，复用同一套建表逻辑。
def init_db(bind: Engine | None = None) -> None:
    import db_models  # noqa: F401  # 关键：必须被 import，模型才注册进 Base.metadata
    Base.metadata.create_all(bind=bind or engine)


# ── 6. 种子数据：让「刚建好的空库」立刻能登录 ───────────────────────
# 幂等：已存在的用户名直接跳过，反复启动不会插重复行，也不会改你手动改过的密码。
# ⚠️ 生产环境不要用它（.env 里 DB_AUTO_SEED=false 关掉），
#    真实账号应该走注册接口 + 管理员审批。
DEFAULT_USERS = (
    {"username": "zihao", "password": "123456", "role": "admin"},
    {"username": "test", "password": "123456", "role": "user"},
)


def seed_default_users(session: Session | None = None) -> int:
    """插入默认账号，返回本次真正新增的条数。不传 session 就自己开一个。"""
    from common.security import pwd
    from db_models import User

    owns_session = session is None
    db = session or SessionLocal()
    inserted = 0
    try:
        # 一次查出所有已存在的用户名，避免「循环里查库」的 N+1 问题
        existing = set(db.scalars(select(User.username)).all())
        for spec in DEFAULT_USERS:
            if spec["username"] in existing:
                continue
            db.add(
                User(
                    username=spec["username"],
                    hashed_password=pwd.hash(spec["password"]),
                    role=spec["role"],
                )
            )
            inserted += 1
        db.commit()
    finally:
        if owns_session:
            db.close()
    return inserted
