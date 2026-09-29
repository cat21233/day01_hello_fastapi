# day-032 复盘：从「import 期读配置」到 Docker 容器化

> 覆盖 9-23（day-031）与 9-24（day-032）两天。
> 写法：**先说哪些是你亲手做的、哪些是你看着做的** —— 这个区分比列知识点更重要。

---

## 一、你亲手做的（9-23，含金量最高的那一批）

| # | 动作 | 你怎么做的 | 结果 |
|---|---|---|---|
| 1 | `llm_service/client.py` —— `_client` 惰性化 | **先自己写了一版错的**（`@property def _client` + `__init__` 里 `self._client = None`）→ 被指出同名死路 → 自己改成门 `_client` / 仓库 `client` | ✅ 三证通过 |
| 2 | `llm_service/factory.py` —— 表挪进函数 | 照对照代码改：模块级 `_PROVIDERS` 常量 → `def _providers()` 内建 `table` 再过滤 | ✅ 藏 `.env` 打桩生效 |
| 3 | `tests/conftest.py` —— 加 autouse fixture | 自己写 `stub_llm_config(monkeypatch)`，造 dummy key + 清缓存 | ✅ 藏 `.env` 从 8 failed → 39 passed |
| 4 | Git 八拍「无提示复现」 | 全程自己走，我只在事后验收 | ✅ 走完，但踩了 3 个坑（见第三节） |
| 5 | 两道自检题 | 「模块级只读一次、改进后每次调用都读」「autouse 在同级目录下运行所以能修复」 | ✅ 两题都对 |

**这 5 项是你自己敲进去的** —— 所以下面的知识你是有肌肉记忆的。

---

## 二、你看着做的（9-24 Docker，参与度低）

| 动作 | 谁做的 |
|---|---|
| 拍板「今晚补 Dockerfile 而不是 Function Calling」 | **你**（这是对的决策 —— 关键路径优先） |
| 处理 Docker Desktop 引擎没起来 | 你（点窗口/重启） |
| 读 `main.py` / `config.py` / `common/logger.py` 摸清依赖边界 | 我 |
| 排查 `docker pull` 卡死 20 分钟 | 我（判别实验：小镜像速测） |
| 写 `Dockerfile`（三阶段）+ `.dockerignore` | 我 |
| 跑三关验收、抓出 `.pyc` 真 bug 并修掉 | 我 |

**实话**：这一轮你是**监工**，不是**施工**。看懂了 ≠ 会写。
9-26 交付之后，Dockerfile 你自己从零写一遍（不看这份），才算真的拿到手。

---

## 三、学到了什么（分三层，越往下越值钱）

### 第 1 层：机制级（知道"为什么"）

**① property 的门与仓库必须异名**

```python
class A:
    @property
    def x(self): ...      # ← 门
    def __init__(self):
        self.x = None     # ← 想当仓库，但写的是门名 → AttributeError（无 setter）
```

两条死路，都实测过：
- 同名赋值 → `AttributeError: property 'x' of 'A' object has no setter`（**实例化就炸**，不是访问时）
- 只删赋值、getter 里自读自写 → `RecursionError`

**原理一句话**：Python 找属性时，**类里的 data descriptor（property 就是）优先于实例 `__dict__`**。所以同名时那个"仓库位"永远轮不到。

**② 模块级常量 = import 那一刻就固化了**

```python
_TABLE = {"a": cfg.x}              # ❌ import 期读一次，之后再改 cfg 也没用
def _table(): return {"a": cfg.x}  # ✅ 每次调用现读
```

实测证据：藏 `.env` 后 `settings.deepseek_api_key = 'test-key'`，settings 字段**确实变了**，但 `_PROVIDERS` 仍是 `[]` → 打桩打不动它。

**同一个文件里的天然对照组**：`get_client` 的表在模块级（中毒）、`get_model` 的表在函数内（免疫）。

**③ conftest.py 的作用域由位置决定**

> **conftest 在哪一层，管哪一层；autouse 不用喊，自动上。**

所以 `tests/conftest.py` 里一个 autouse fixture 能连带修好 `test_infra.py` 的启动校验失败。

### 第 2 层：流程级（Git 三个静默失败 —— 今天最硬的一课）

| 动作 | 它给你的假象 | 真相 | 唯一自查 |
|---|---|---|---|
| 跳级 merge | `Already up to date.` | 要合的东西**不在 dev 里** | 期望输出必须以 `Fast-forward` 开头 |
| 裸 `git push` | `44f3eeb..1ac43a9 main -> main` | 只推当前分支，**dev 纹丝不动** | `git branch -vv` 不能有 `[ahead N]` |
| `-m` 当 `--amend` | 提交成功 | message 与内容**换了身** | 每次 commit 后 `git show --stat HEAD` |

**共同点：输出看起来全是"成功"。** 光看输出判断不了，必须**主动核对 sha**。

配套的返工判据：

| 情况 | 怎么办 |
|---|---|
| **未推送**的最新 message 错 | `git commit --amend`（5 秒，零风险） |
| **未推送**且内容装错 commit | `git reset --soft <基线>` → 重新分刀 |
| **已推送** | **别动**（改历史会打乱别人），记教训 |

### 第 3 层：方法论级（这两条会跟你很久）

**① 期望值必须来自源码或实测，禁止凭印象。**

我自己在这两天犯了两次，都被你会话里纠正过来：
- 说 `/docs` 返回 0 字节 → 实际 1018 字节（是 `-o /dev/null` 写不进去的测量假象）
- 说 `GET /items/` "应该 401" → 翻 `routers/items.py:17`，那个路由**根本没挂鉴权**，200 才对

**②「藏起 .env 复现线上环境」是排查"本地绿线上红"的标准手法。**

比推十次 commit 试错快得多。同一个思路的两次应用：
- 验证三处治本 → 藏 `.env` 跑测试（8 failed → 39 passed）
- 诊断拉镜像卡死 → 先拉 13KB 的 hello-world 做判别实验（4.5s ✅ → 锁定不是通道问题）

---

## 四、明天的账

**已过**：✅ CI｜✅ Docker 三关（容器内 39 passed）｜✅ 三处治本｜✅ 八拍复现
**只剩**：⏳ **9-26 交付上线 + `v0.1` tag**（stage-1 最后一根柱子）

**待提交 3 项**：

```
 M tests/conftest.py     ← conftest 格式修正（独立一刀：style(test): ...）
?? Dockerfile            ┐
?? .dockerignore         ┘ 同一故事，一刀：build(docker): ...
```

**还没自己写过的**：Dockerfile 从零手写、`git show --stat HEAD` 自查习惯没定型。
