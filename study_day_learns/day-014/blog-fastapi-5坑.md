# 学 FastAPI 第一周，我踩过的 5 个坑

> 背景：大二学生，从零学 FastAPI，第一周亲手把路由、参数校验、嵌套模型、子依赖鉴权、SSE 流式、异步调用外部 API 全部跑通。
> 这篇文章记录我踩过的 5 个坑——每个都曾让我卡住半小时以上，希望你能绕过去。

如果你也在学 FastAPI，或者正打算学，这篇文章值得你花十分钟读完。我踩的这 5 个坑里，有 3 个是"看文档能懂、动手就错"的经典陷阱，另外 2 个是"懂了原理但写代码时大脑短路"的真实事故。所有代码都是我实际跑过的，错误代码也是我真实写过的——不是编的。

---

## 坑 1：`=` 和 `:` 写错，接口直接 500

### ① 我遇到的

Day 3 的闭卷练习：写一个 `POST /orders/{user_id}` 接口，订单数据从 JSON 请求体接收，user_id 从 URL 路径接收。我信心满满地写完，打开 `/docs` 一测——**接口直接 500 Internal Server Error**。

打开 Swagger 一看，参数区显示 `order` 的类型是 `any`，位置在 `(query)`，请求体那一栏是空的（`-d ''`）。我当时整个人是懵的："我明明定义了 Order 模型，FastAPI 怎么不认？"

### ② 错误代码

```python
@app.post("/orders/{user_id}")
def create_order(order=Order):
    user_id: int = Path(..., gt=0)   # 还写在了函数体里
    return {"ok": True, "user_id": user_id, "order": order}
```

### ③ 为什么错

两个错误，同一个根源：**把"声明参数"写成了"函数里赋值"**。

- `order=Order` 里的 `=` 是**默认值**，不是类型声明。FastAPI 读的是**函数签名**（`def` 那一行），它看到 `order=Order` 会以为："哦，这是个查询参数，默认值是 Order 这个类"。于是 Swagger 显示 `any (query)`，body 为空，函数返回时 FastAPI 想把 `Order` 类本身序列化成 JSON → 失败 → 500。
- `user_id: int = Path(...)` 写在函数体里，FastAPI 根本看不到——它只扫描签名参数列表。等函数执行到这一行，参数早就收集完了。

**正确姿势**：`=` 是默认值，`:` 才是类型注解。要让 FastAPI 识别"这是请求体"，必须写 `order: Order`（冒号+类型）。所有需要 FastAPI 注入的东西（Path/Query/Depends/模型），**必须写在 `def` 的参数列表里**。

### ④ 正确写法

```python
@app.post("/orders/{user_id}")
def create_order(order: Order, user_id: int = Path(..., gt=0)):
    return {"ok": True, "user_id": user_id, "order": order}
```

### ⑤ 验证结果

改完后重启服务（沙箱里 `--reload` 不生效，必须手动 Ctrl+C），Swagger 里 `Request body` 正常显示 Order schema，填 `{"product_name": "键盘", "quantity": 2}` 返回 200。

---

## 坑 2：Query / Path / Field 傻傻分不清

### ① 我遇到的

同一天的另一个练习：写 `Product` 模型，`name` 必填最长 50，`price` 必填大于 0。我写完后自己检查，觉得没问题——结果把校验写在了**函数体里**，还套了 `Path()`：

```python
def create_product(product=Product):
    name: str = Path(..., max_length=50)   # 校验写错位置，还用错了校验器
    price: int = Path(..., gt=0)
```

### ② 我当时以为的判断规则

我给自己总结了一条"捷径"：**Path 用在 POST，Query 用在 GET，Field 用在模型里**。看起来顺口，实际上是错的。

### ③ 为什么错

因为判断标准根本不是 HTTP 动词，而是——**这个值从哪来**：

| 值从哪来 | 用哪个 | 写在哪 |
|---------|--------|--------|
| URL 路径里（`/items/5` 的 `5`） | `Path` | 函数签名 |
| URL 问号后（`?q=xxx`） | `Query` | 函数签名 |
| JSON 请求体里 | `Field` | 模型类内部 |

反例能立刻击碎"Path=POST"的错误直觉：`GET /items/{item_id}` 里的 `item_id` 明明就是 GET 请求，但它用 `Path`。因为它的值在 URL 路径里，跟 GET 还是 POST 毫无关系。

### ④ 口诀

**函数参数用 Query / Path，模型字段用 Field。**
问自己"值从哪来"：URL → Query/Path；body → Field。

### ⑤ 验证结果

后面两道练习（Product、Order）我全部一次用对。这个坑踩过一次后，就形成了肌肉记忆。

---

## 坑 3：Optional 到底干嘛的

### ① 我遇到的

D3 学嵌套模型时，看到 `age: Optional[int] = None`，我第一反应是："`Optional` 就是让字段可以不填的。"听起来很合理，对不对？**但功劳记错了人。**

### ② 关键认知

`Optional[int]` 和 `= None` 分工不同：

- **`Optional[int]` 是"许可证"**：允许这个字段的值是 `None`。它只声明"类型可以是 int，也可以是空"。
- **`= None` 才是"执行者"**：提供默认值，让字段**不填时自动变成 None**。

所以：

```python
age: Optional[int] = None   # 选填：不传就是 None ✅
age: Optional[int]          # 必填：但不允许传 null 报错，只是允许你显式传 null ⚠️
```

看到区别了吗？只写 `Optional[int]` 不带默认值，Pydantic 依然要求你**必须传**（传 `null` 可以，但不能不传）。"能不能省略"看默认值，跟 Optional 没关系。

### ③ 代码对照

```python
from typing import Optional

class User(BaseModel):
    name: str                      # 必填
    age: Optional[int] = None      # 选填，不传就是 None
    # age2: Optional[int]          # 如果这样写：必填，但允许传 null
```

### ④ 验证结果

在 `/users/` 接口测试：不传 `age`，请求成功，`age` 变成 `None`。而如果我把 `age` 改成没有默认值的写法，不传 `age` 直接 422 校验错误——亲眼看到区别，比背概念牢靠多了。

---

## 坑 4：Web 接口里写 `input()`，服务直接卡死

### ① 我遇到的

D4 学 SSE 流式响应，题目是"接收一个名字，把 `Hello, 名字` 逐字符流式返回"。我当时的思路是这样的："程序运行到这里，需要用户输入名字，那就 `input()` 问一下呗。"于是写了：

```python
async def Hello():
    name = input("请输入名字:")   # 我以为这是"让用户输入"
    for ch in f"Hello, {name}":
        yield f"data: {ch}\n\n"
        await asyncio.sleep(0.15)
```

### ② 为什么错

这是我一周里**认知转变最大**的一个坑。`input()` 是**命令行脚本**的 IO：程序停在终端，等你敲键盘。但 FastAPI 服务跑在服务器上：

1. **没有键盘可等**——服务端没有终端窗口弹出来让你输入。
2. **更本质的**：HTTP 是**请求-响应**协议。客户端发一个请求，这个请求**自带所有需要的数据**（URL、Header、Body），服务端处理完就返回。服务端**永远没有能力"反过来问"客户端要东西**——协议上就没有这个通道。
3. 就算有键盘，一个请求卡在 `input()` 上，事件循环被占住，后面一万个请求全堵死。

所以 web 接口的参数，只能由**客户端主动带过来**——这就是 `Query` 存在的意义。

### ③ 正确写法

```python
@app.get("/stream/greet")
async def stream_greet(name: str = Query(..., description="你的名字")):
    return StreamingResponse(greet_stream_generator(name), media_type="text/event-stream")
```

### ④ 验证结果

`curl -N "http://127.0.0.1:8000/stream/greet?name=叶梓皓"`——看到 `H`、`e`、`l`、`l`、`o`、`叶`……一个字一个字蹦出来，每 0.15 秒一个。那个瞬间我真正理解了：**web 世界里，是客户端把数据寄过来，服务端收下处理，不是服务端停下来问。**

---

## 坑 5：`time.sleep` vs `await asyncio.sleep`，差出 3 倍

### ① 我遇到的

D6 的 async 专项练习：写个脚本对比"同步顺序请求 3 个外部 API"和"并发请求同样 3 个"的耗时。我第一版就把 `fetch_user` 写成了 `def`（漏了 `async`），函数体里的 `async with` 直接语法报错；改好后又因为顶层函数前面多了一个看不见的空格，报了一下午的 `IndentationError`。这些坑都是"看着对、跑起来炸"的类型，好在最后都解决了。

### ② 为什么 await 更好

`time.sleep(1)` 是**阻塞**的：这 1 秒里整个线程被卡死，啥也干不了。而 `await asyncio.sleep(1)` 是**非阻塞**的：它把控制权交还给事件循环，这 1 秒里事件循环可以去处理别的请求/任务，时间到了再回来继续。

这就是 FastAPI 高并发的秘密：**await 等待 I/O 时，事件循环在服务别人**。而大模型的 API 调用正是最典型的"长时间 I/O"——一次请求几秒钟，如果用同步方式，服务器等于被一个用户占死。

### ③ 实测数据

```text
===== 同步版 =====
同步耗时: 2.26 秒        # 3 个请求串行，一个等完再发下一个

===== 并发版 =====
并发耗时: 1.24 秒        # asyncio.gather 同时发出，总耗时 ≈ 最慢那一个
```

用 `asyncio.gather` 并发，3 个请求的总耗时从 2.26s 降到 1.24s，**省了约 45% 的时间**。

### ④ 结论

为什么没到理想的 3 倍？因为 TCP 连接建立、TLS 握手这些固定开销**没法并发**——每个请求都得单独来一遍。但如果换成调大模型 API（单次请求好几秒），网络等待占比极高，并发几乎能逼近 3 倍提速。所以**异步是 Agent/LLM 应用的必备技能**，不是可选项。

---

## 结尾

一周前，我以为会写 Python 就约等于会写后端；一周后我才明白，**Web 后端是一套完全不同的思维模型**——请求-响应、参数注入、异步事件循环。这 5 个坑是我的学费，但把它们写成文章后，它们从"挫折"变成了"作品"。

下一步我要学 JWT 鉴权（把 Day 3 那个简化版 token 校验升级成工业级），然后走向 Agent 应用。如果你也在学 FastAPI，欢迎对照检查——这 5 个坑，你踩了几个？

---

*本文基于真实学习经历，代码均为亲手跑通的版本。*
