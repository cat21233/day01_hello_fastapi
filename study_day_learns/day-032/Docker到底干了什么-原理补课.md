# Docker 到底干了什么 —— 一晚工作的原理补课

> 这份文档存在的原因：9-24 那一晚我（AI）把 Dockerfile 写完、验收跑完，但**没跟你讲过原理**。
> 那不是教学，是交付。这里把欠的课补上。
>
> 读法建议：先读第 1-4 节（概念），再去第 8 节动手，最后回头看第 5-6 节（我们那份文件的逐段拆解）。

---

## 1. 问题：为什么需要 Docker

**故障场景**（你一定遇到过类似的）：

> 你本地跑得好好的 FastAPI，发到服务器上就启动不了。或者：你今天能跑，明天 `pip install` 完就崩了。

原因通常有四个，而且**全都不在你的代码里**：

| 漂移源 | 例子 |
|---|---|
| 系统库版本 | 你机器上碰巧有 `libgomp.so`，服务器上没装 |
| Python 版本 | 你是 3.12，CI 是 3.10，某个语法不支持 |
| 依赖版本 | 你昨天装的 `openai==2.1`，别人今天装到 `2.3`，行为变了 |
| 环境变量 / 路径 | 大小写敏感、`/` 与 `\`、时区 |

**Docker 的解法**：不打包你的代码，**打包整个运行环境**。

```
传统部署：交付「代码」 → 别人的机器用别人的环境跑
Docker  ：交付「代码 + 操作系统 + Python + 所有依赖」的一体快照
```

一句话：**Docker 让"在我机器上能跑"变成一个可搬运的东西。**

---

## 2. 镜像 = 类，容器 = 实例（最重要的一个类比）

你懂 Python 的类和实例，那就是 Docker 的全部核心。

| Docker | Python 类比 | 说明 |
|---|---|---|
| **镜像（image）** | **类（class）** | 只读的模板，躺在磁盘上，不运行 |
| **容器（container）** | **实例（object）** | 镜像跑起来的进程，可创建 N 个，互不干扰 |
| `docker build` | `class` 定义 | 造"类"——把配方变成模板 |
| `docker run` | `实例化` | 造"实例"并让它跑起来 |
| `docker rmi` | 删掉类定义 | 删镜像 |
| `docker rm` | `del obj` | 删容器 |

**关键推论**（这个推论解释了半个 Docker 的用法）：

> 一个镜像可以跑出 100 个容器，它们**互不影响**。你在容器 A 里改了文件、删了东西，容器 B 完全不知道，镜像本身也不变。

这就是为什么容器"坏了就删掉重开"是标准操作 —— 反正模板还在。

```
镜像 day01-fastapi:v0.1  (只读模板)
   ├─ 容器 day01   ← 你昨晚起的那个，已删
   ├─ 容器 day02   ← 可以再起一个，同时跑
   └─ 容器 day03   ← 再起一个
```

---

## 3. 分层：Dockerfile 里的顺序为什么讲究

### 3.1 每条指令 = 一层

Dockerfile 里每条**会改变文件系统**的指令，都会产生一个**只读层**（layer）。这些层像千层饼一样叠起来。

```
runtime 镜像的层（自下而上）：
  第 1 层  ← python:3.12-slim 基础镜像（179MB）
  第 2 层  ← ENV 环境变量
  第 3 层  ← ARG + WORKDIR
  第 4 层  ← COPY requirements.txt        ← 这一层只装"清单"
  第 5 层  ← RUN pip install ...           ← 装好的 45 个包（最重的一层）
  第 6 层  ← RUN useradd appuser
  第 7 层  ← COPY main.py config.py ...    ← 你的代码
  第 8 层  ← USER / EXPOSE / CMD
```

### 3.2 层是可以复用的 —— 这就是"缓存"

`docker build` 时，Docker 逐层检查：**这条指令 + 它的输入没变 → 直接用上次的成品（CACHED）**。

一旦某一层失效，**它后面所有层全部失效**。

### 3.3 所以顺序是这么来的

我们 Dockerfile 里的这段是**刻意排的**：

```dockerfile
COPY requirements.txt ./                  # 第 4 层：只复制"依赖清单"这个文件
RUN pip install -r requirements.txt       # 第 5 层：装依赖（约 82 秒）

# ... 中间其它层 ...

COPY main.py config.py ./                 # 第 7 层：复制代码
COPY common/ ./common/                    # 第 8 层
COPY routers/ ./routers/                  # 第 9 层
COPY llm_service/ ./llm_service/          # 第 10 层
```

**为什么不能写成这样**：

```dockerfile
COPY . .                                  # ❌ 代码和依赖混在一层
RUN pip install -r requirements.txt
```

因为 `COPY . .` 这一层包含了你的代码 —— **你改一行代码，这一层就变了，它后面的 `RUN pip install` 也全废，每次 build 都要重装 82 秒的依赖。**

按我们的排法，改代码只影响第 7 层往后 —— **依赖层（第 5 层）稳稳命中缓存。**

### 3.4 实测数字（昨晚真跑出来的）

| 场景 | 耗时（实测） | 依赖层 |
|---|---|---|
| 什么都没改（全缓存） | **3.0 秒** | CACHED |
| **只改代码**（改 `main.py`，追加一个空行） | **7.7 秒** | **CACHED** ← 关键 |
| 依赖层失效（改了 `--build-arg PIP_INDEX_URL`，用到它的 `RUN` 层重跑） | **82 秒** | 重装 |

**顺序错了，你每次改代码都是 82 秒。** 7.7 秒里，绝大部分是"重建后面几层 + 导出镜像"的固定开销，**装依赖那 50 秒一秒钟都没花**。

> 数据来源：9-24 深夜补课时真跑的（`docker build --progress=plain`，`time` 计时）。原文写"2-3 秒"是我的推测，实测是 7.7 秒 —— 按我们的规矩，期望值必须实测。

---

## 4. 构建上下文：`docker build ... .` 最后那个点是什么

这是我们跑的命令：

```bash
docker build -t day01-fastapi:v0.1 .
                                        ↑ 这个点 = 构建上下文（context）
```

它的含义：**把当前目录整个打包，发给 Docker 引擎**。

不是"把当前目录复制进镜像"——是**发给引擎**。送过去之后，Dockerfile 里的 `COPY` 再从这包东西里挑。

### 所以 `.dockerignore` 管的是什么？

**它管的是"打包/传输"这一步的排除清单**，不是"镜像里的排除清单"。（副作用才是影响镜像内容。）

| 如果没写 `.dockerignore` | 后果 |
|---|---|
| `.venv/`（几百 MB，还是 Windows 版） | 每次 build 都白传一遍（而且进 Linux 镜像根本跑不了） |
| `models/`（92MB 本地模型权重） | 同上白传 |
| **`.env`（API key）** | **万一以后有人把 COPY 改成 `COPY . .`，key 就进镜像了** |

**这就是为什么排除清单的第一优先级是 `.env`** —— 它现在是一道**冗余安全闸**：本 Dockerfile 的 COPY 全是显式路径，不会误带它；但清单在那儿，将来改坏了也兜得住。

---

## 5. 我们那份 Dockerfile 逐段拆解

### 5.1 三个环境变量（第 19-22 行）

```dockerfile
ENV PYTHONDONTWRITEBYTECODE=1   # 不生成 __pycache__
ENV PYTHONUNBUFFERED=1          # 日志立刻刷出来
ENV PIP_NO_CACHE_DIR=1          # pip 的下载缓存不留在层里
```

| 变量 | 不写会怎样 |
|---|---|
| `PYTHONDONTWRITEBYTECODE` | 容器里生成一堆 `.pyc`（容器里没人会复用它们，纯白占体积） |
| `PYTHONUNBUFFERED` | **`docker logs` 什么都看不到** —— Python 把输出缓冲在内存里，不刷出来。这条昨晚是刚需 |
| `PIP_NO_CACHE_DIR` | pip 下载的 whl 文件留在层里，白占几十 MB |

> 这三条都是"容器场景特有"的调优 —— 你在本地开发时完全不需要。

### 5.2 `ARG PIP_INDEX_URL`（第 27 行）

```dockerfile
ARG PIP_INDEX_URL=https://pypi.org/simple
```

| | `ARG` | `ENV` |
|---|---|---|
| 何时生效 | **只在 build 期间** | build + 运行时都生效 |
| 谁能改 | `--build-arg` 传 | 镜像里写死，运行时可 `-e` 覆盖 |
| 用途 | **构建参数**（选源、选版本） | **运行配置**（key、端口） |

**为什么默认写官方 PyPI**：镜像要能给别人用。别人 `git clone` 之后 `docker build` 就能成功，不该依赖中国的镜像源。国内构建慢时用：

```bash
docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple -t day01-fastapi:v0.1 .
```

**实测**：清华源 21 秒 vs 官方 82 秒。

> ⚠️ **ARG 不跨阶段继承** —— 这是真实的坑。`base` 阶段声明了 `ARG`，`test` 阶段想用必须**重新声明一次**（我们第 42 行就是为这个）。

### 5.3 `FROM python:3.12-slim AS base`（第 14 行）

- `python:3.12-slim` = 官方 Python 3.12 精简版（179MB，完整版 `python:3.12` 是 1GB+）
- `AS base` = **给这个阶段起个名字**，后面别的阶段可以 `FROM base` 引用它

### 5.4 非 root（第 70、79 行）

```dockerfile
RUN useradd --create-home --uid 1000 appuser
...
USER appuser
```

**为什么**：容器默认以 root 运行。万一应用被攻破（比如某个依赖有 RCE 漏洞），攻击者在容器内就是 root。

`USER appuser` 之后，攻击者拿到的是普通用户 —— 权限小一圈。

昨晚验证：`docker exec day01 id` → `uid=1000(appuser)`。

> 面试常问的一道题：「容器里为什么要用非 root？」答案就是这个 + "最小权限原则"。

### 5.5 `--host 0.0.0.0`（第 85 行）

```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**这是最容易踩的一个坑**：

| 监听地址 | 含义 |
|---|---|
| `127.0.0.1` | 只接受**容器自己内部**的连接（默认值） |
| `0.0.0.0` | 接受**任何来源**的连接（容器外也能连） |

你 `-p 8010:8000` 做端口映射时，流量是从"容器外部"进来的。如果应用只监听 `127.0.0.1`，映射进来的请求**进不到应用** —— 表现为"容器活着（`docker ps` 显示 Up）、但浏览器连不上"。

### 5.6 `.dockerignore` 里那个 `**/`

```dockerignore
**/__pycache__/
**/*.py[cod]
```

**这是昨晚真踩到的坑**。原来写的是：

```dockerignore
__pycache__/          # ❌ 只匹配根目录那一层
*.py[cod]             # ❌ 一样
```

结果重建镜像后进去一看：

```
/app/llm_service/__pycache__/factory.cpython-312.pyc     ← 还是进来了
/app/routers/__pycache__/auth.cpython-312.pyc
```

**根因**：`.dockerignore` 的匹配规则里，`*` **不跨 `/`**（跟 shell 的 glob 一样的道理，不是正则）。

- `__pycache__/` 只匹配 `<上下文根>/__pycache__/`
- `**/__pycache__/` 匹配**任意深度**的 `__pycache__/`

改成 `**/` 后重建：`.pyc` 归零，`/app` 从 **208K → 112K**。

---

## 6. 三阶段构建：为什么要 test 和 runtime 分开

```
       ┌─────────────────────────────────────┐
       │  stage 1: base                       │
       │  python:3.12-slim                    │
       │  + requirements.txt（生产依赖）        │
       └──────────────┬──────────────────────┘
                      │
        ┌─────────────┴──────────────┐
        ▼                            ▼
┌───────────────────┐      ┌──────────────────────┐
│ stage 2: test     │      │ stage 3: runtime     │
│ base              │      │ base                 │
│ + requirements-dev │      │ + main.py / routers/ │
│ + tests/           │      │ + llm_service/       │
│ + 生产代码          │      │ + 非 root appuser     │
│                   │      │ + EXPOSE 8000        │
│ CMD pytest        │      │ CMD uvicorn          │
└───────────────────┘      └──────────────────────┘
   ↑ 只用来跑测试              ↑ 这才是交付物
   不进最终镜像                320MB
```

**关键规则**：

```bash
docker build -t day01-fastapi:v0.1 .              # 默认只产出【最后一个】阶段 = runtime
docker build --target test -t day01-fastapi:test . # 指定产出 test 阶段
```

**为什么要分**：

| 理由 | 说明 |
|---|---|
| 体积 | `pytest` / `pytest-cov` / `pytest-asyncio` 三件套不该进生产镜像 |
| 攻击面 | 镜像里少一个包，就少一个潜在漏洞入口 |
| 干净 | 生产镜像里**没有测试代码、没有学习归档** |

**实测对比**：

| 镜像 | 体积 | 用途 |
|---|---|---|
| `day01-fastapi:test` | 341MB | 只在 CI / 本地跑测试，**永不上线** |
| `day01-fastapi:v0.1` | 320MB | 交付物，`docker run` 起服务 |

> 面试话术：「多阶段构建让测试依赖和测试代码不进生产镜像，缩小体积与攻击面。三阶段共用 base 依赖层，缓存还能共享。」

---

## 7. 那晚每条命令在干什么（对照表）

| 你看到的命令 | 它在干什么 | 类比 |
|---|---|---|
| `docker build -t day01-fastapi:v0.1 .` | 按 Dockerfile 造镜像，打上标签 `v0.1` | 定义类 |
| `docker build --target test -t day01-fastapi:test .` | 只造到 test 阶段 | 定义一个"测试用类" |
| `docker run --rm day01-fastapi:test` | 用 test 镜像起一个容器并运行它（默认 CMD = pytest），跑完销毁 | 实例化 + 调用 |
| `docker run -d --name day01 -p 8010:8000 -e K=V day01-fastapi:v0.1` | 后台起服务容器 | 实例化并常驻 |
| `docker exec day01 id` | 在**正在运行**的容器里执行一条命令 | 远程进机器敲一条命令 |
| `docker logs day01` | 看容器的 stdout（这就是为什么要 `PYTHONUNBUFFERED`） | 看日志 |
| `docker stop day01 && docker rm day01` | 停 + 删容器 | `del obj` |
| `docker images` | 列出本地镜像 | 列出已定义的类 |
| `docker ps -a` | 列出所有容器（含已停的） | 列出所有实例 |

### 那几个 flag 的意思

| flag | 全称 / 含义 |
|---|---|
| `-t` | tag，给镜像起名 `名字:标签` |
| `-d` | detached，后台运行 |
| `--rm` | 容器退出后自动删除（不然垃圾容器越堆越多） |
| `-p 8010:8000` | **端口映射：`宿主机:容器`**。浏览器访问 `localhost:8010` → 转给容器的 8000 |
| `-e K=V` | 传环境变量进去 **← 这就是为什么 `.env` 不用进镜像** |
| `--target test` | 只构建到指定阶段 |
| `--progress=plain` | 输出完整的构建日志（默认那个动态界面会覆盖历史） |

**`-e` 这条要想通**：我们的代码用 `pydantic-settings` 读配置，它的查找顺序是"环境变量优先于 `.env` 文件"。

镜像里**没有 `.env`**（`.dockerignore` 排掉了 + `COPY` 也没显式带它），所以 `-e DEEPSEEK_API_KEY=xxx` 就自然生效了 —— **这就是"12-factor app"的配置外置原则**：代码进镜像，配置从外面注入。

同一份镜像，用不同的 `-e` 就能连不同的环境（测试/生产）—— 不用重新构建。

---

## 8. 动手实验（4 个，都有判别力）

> 判别力 = 改与不改，结果不同。跑完你会**亲眼看到**现象，不是听我说。

### 实验 1 · 看见分层（30 秒）

```bash
docker history day01-fastapi:v0.1 --no-trunc --format "table {{.Size}}\t{{.CreatedBy}}" | head -12
```

**看什么**：最下面几层是基础镜像，中间最大的一层是 `pip install`（约 50MB），最上面几层是你的代码（只有几十 KB）。

---

### 实验 2 · 进容器里看"什么进来了、什么没进来"（3 分钟，**最有价值**）

```bash
docker run --rm -it day01-fastapi:v0.1 sh
```

进去之后依次敲：

```bash
ls -a /app                      # 看生产文件清单
ls /app/.env                    # 期望：No such file or directory
ls /app/tests                   # 期望：No such file or directory
ls /app/study_day_learns        # 期望：No such file or directory
find /app -name "*.pyc"         # 期望：空（.dockerignore 生效）
id                              # 期望：uid=1000(appuser) gid=0(root)
python -c "import os; print(os.getenv('DEEPSEEK_API_KEY'))"   # 期望：None（因为没传 -e）
exit                            # 退出
```

**这一趟跑完，你就知道"多阶段 + .dockerignore"到底做了什么** —— 不是听我说，是你自己 `ls` 出来的。

---

### 实验 3 · 亲眼看到分层缓存生效（2 分钟，**第二有价值**）

```bash
cd C:/Users/yizihao/projects/day01-hello-fastapi
```

**先改一行代码**（随便改什么，加个注释就行）：

```bash
echo "" >> main.py
```

> 这是往 `main.py` 末尾追加一个空行 —— 无害，实验后 `git checkout main.py` 还原。

**然后重建，看输出**（必须加 `--progress=plain`，否则看不到每步状态）：

```bash
time docker build --progress=plain -t day01-fastapi:v0.1 . 2>&1 | grep -E "^#[0-9]+ \[|CACHED|DONE"
```

**你会看到的（这是我实测的原样输出）**：

```
#7  [base 3/4]    COPY requirements.txt ./        CACHED
#8  [base 4/4]    RUN pip install -r ...           CACHED     ← 依赖层一秒钟都没花
#9  [runtime 1/5] RUN useradd ...                  CACHED
#10 [runtime 2/5] COPY main.py config.py ./        DONE 0.1s  ← 从这层开始重建
#11 [runtime 3/5] COPY common/ ./common/           DONE 0.1s
#12 [runtime 4/5] COPY routers/ ./routers/         DONE 0.1s
#13 [runtime 5/5] COPY llm_service/ ./llm_service/ DONE 0.1s
```

**耗时**：`real 7.767s`（不是 82 秒）

**怎么看这个结果**：第 8 步是"装 45 个包"那一步，它显示 `CACHED` —— 意味着**它被整层复用了**。第 10 步开始重建，是因为 `main.py` 变了，而它在这条链上位于第 8 步**之后**，所以只影响它自己往后。

> 反过来说：如果你改的是 `requirements.txt`，第 8 步就会失效 —— 而它后面还有 4 层，全部一起重来。**这就是"最贵的那层要尽量往下压"的含义。**

**然后还原**：

```bash
git checkout main.py
```

**为什么这个实验有判别力**：你能亲眼看到"依赖层 CACHED"。如果 Dockerfile 顺序写错了（`COPY . .` 在 `pip install` 前面），这里会是 `DONE 82s`。**顺序的重要性，用数字砸给你看。**

---

### 实验 4 · 验证"镜像只读、容器可写"（1 分钟）

```bash
docker run --rm day01-fastapi:v0.1 sh -c "echo 'I broke it' > /app/main.py; head -1 /app/main.py"
```

**期望**：输出 `I broke it`（容器里确实被改了）

```bash
docker run --rm day01-fastapi:v0.1 sh -c "head -1 /app/main.py"
```

**期望**：输出**原来的第一行**（`from fastapi import FastAPI` 之类）

**结论**：改容器里的文件**不影响镜像**。容器是"镜像 + 一层可写层"，删掉容器，改动就没了。
这就是"容器坏了就删掉重开"能成为标准操作的原因。

---

## 9. 自检题（答得出来才算真懂）

1. **镜像和容器是什么关系？** 用 Python 的什么概念类比？
2. **为什么 `COPY requirements.txt` 要写在 `COPY . .`（或 COPY 代码）**前面**？** 答得出"改代码不会让依赖层失效"就对了。
3. **`.dockerignore` 管的是"镜像里的排除"还是"传输时的排除"？** 第 4 节有答案。
4. **`ARG` 和 `ENV` 的区别是什么？** 提示：一个只在 build 期间存在。
5. **为什么 `CMD` 里要写 `--host 0.0.0.0`？** 不写会有什么现象？
6. **为什么要多阶段构建？** 说两条理由。
7. **`-e DEEPSEEK_API_KEY=xxx` 为什么能生效？** 提示：pydantic-settings 的查找顺序 + `.env` 不在镜像里。

---

## 附：一个常见误区

> "我本地有 `.venv`，Docker 是不是会用它？"

**不会**。镜像是全新的 Linux 环境，`.venv` 被 `.dockerignore` 排掉了（而且它是 Windows 版，进了 Linux 也用不了）。

镜像里的依赖，是 `RUN pip install -r requirements.txt` 那一步**在容器里重新装的**。

**这就是 Docker 的价值**：它不依赖你本地的任何东西，所以**在别人机器上也能跑出一模一样的结果**。
