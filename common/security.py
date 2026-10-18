"""密码学工具（全项目共用）。

为什么把 pwd 从 routers/auth.py 挪到这里？
    因为「建表时写种子用户」也要哈希密码，而种子数据属于数据库层。
    如果 db.py 反过来 import routers.auth，就变成「底层依赖上层」，
    一旦 auth 再 import db，立刻循环 import 炸掉。
    → 把共用的东西沉到 common/，两边都往下依赖，依赖方向永远是单向的。
"""

from passlib.context import CryptContext

# bcrypt：自带随机盐，同一个密码每次哈希结果都不一样。
# 所以校验不能用「哈希相等」，必须用 pwd.verify(明文, 哈希)。
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
