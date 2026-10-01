# SSE 流式测试 · 六概念速查卡

> day-046（2026-09-30）· 复述前扫一眼 · 明天抽查用
> 背景：`common/sse.py:26-34` 的 `_frame()` 一行都没被跑过，覆盖率为 0。根因是 39 个测试**从没发过一个 HTTP 请求**。

---

## 一张总图：六个零件在测试生命轴上的位置

```
pytest 收集到 test_xxx
    ↓
[1] fixture 摆现场 ··········· 词 4 fixture + 词 5 monkeypatch
    ↓
[2] TestClient 发请求 ········ 词 3（真的 app，假的只有网线）
    ↓
[3] 服务端真的迭代 body ······ 词 6 SSE 帧格式（id: / data: / 空行）
    ↓
[4] 带 Last-Event-ID 再敲一次 · 词 7
    ↓
[5] 断言 ····················· 词 8（哪一层才有判别力）
    ↓
[6] fixture 拆景（自动）
```

**一句话串起来**：fixture 摆好假上游 → TestClient 从外面敲 → 服务端被迫迭代 body、吐出标准 SSE 帧 → 我们再带断点敲一次 → 用有判别力的断言确认"只补断点之后的"。

---

## 词 3 · TestClient

| 栏 | 内容 |
|---|---|
| 回答什么问题 | 我怎么在 pytest 里**敲自己的接口**？ |
| 一句话 | 一个**留在客户端这一侧**的假客户端，把请求直接递给进程内的 app，不走网络 |
| 项目位置 | `tests/test_protected_stream.py:2`（import）、`:4`（创建）、`:20`（敲）、`:25`（断言） |
| 真 / 假分界 | **假的**：独立进程、监听端口、真 TCP socket、代理/防火墙（外壳层）<br>**真的**：路由匹配、`Depends`、限流中间件、**迭代 body**、路由函数本体（逻辑层） |
| ⚠️ 易错 | ① 它不是"测试用的服务器"，它是**客户端**；② 它不是 `APIRouter`（那是"把接口分类装进应用"，在服务端**内部**）；③ 服务器没"假的"，`client.app is app` 返回 `True` |
| 为什么关键 | 它是**点亮 `_frame` 的唯一途径**——因为只有它会触发"服务端真的去迭代响应体" |

---

## 词 4 · fixture

| 栏 | 内容 |
|---|---|
| 回答什么问题 | 多个测试都要做的同一件准备工作，写在哪？ |
| 一句话 | 测试的「**前置准备 + 事后清理**」，写成一个函数，pytest 按名字自动调用 |
| 怎么生效 | 测试函数把 fixture 名**写成参数** → pytest 去找同名 fixture 并跑它（这叫注入，不用手调） |
| `yield` 是分界线 | `yield` **之前** = setup（摆现场）；`yield` **之后** = teardown（拆现场） |
| 默认 scope | `scope="function"` → **每个测试都重新跑一遍**（实测：`[fresh fixture] 第 1 次被创建` / `第 2 次被创建`） |
| 项目位置 | `tests/conftest.py:4`（`disable_rate_limiting`，`:9-11` 是手工还原）、`:12`（`stub_llm_config`） |
| ⚠️ 易错 | ① `conftest.py` 里的 fixture **不用 import**，pytest 自动发现；② `autouse=True` 表示**不用写参数也生效**（项目里两个都是）；③ 不拆景 → 污染下一个测试 → 拿到"假绿"或"假红" |

---

## 词 5 · monkeypatch.setattr

| 栏 | 内容 |
|---|---|
| 回答什么问题 | 怎么**临时**把真东西换成假的，而且测试结束**自动换回来**？ |
| 一句话 | 测试专用的临时替换器，测试一结束自动还原 |
| 三个参数 | `setattr(①哪个对象, ②"哪个属性名", ③换成什么)` |
| ⚠️ **① 是什么** | **① 是「这东西住在哪儿」的那一层**（模块 / 类 / 实例），**不是**你 import 进来的那个名字 |
| 项目位置 | `tests/conftest.py:17`（换 `settings.deepseek_api_key`）、`:18`（换 `factory._cache`）；`tests/test_llm_stream.py:47`（换 `rl.llm`）、`:52`（换 `rl._expire`） |
| 为什么不用手工赋值 | 手工赋值 + 中间 assert 失败抛异常 → 还原那行**不执行** → 污染后续测试。monkeypatch 由 pytest 保证还原 |
| ⚠️ 硬边界 | 只能换**调用期才读**的东西。模块顶层已经执行完的对象，换掉模块属性也换不掉它内部——这是 `feature/lazy-llm-client` 分支存在的理由 |
| 记忆口诀 | **换住址，不换复印件**。`monkeypatch.setattr(routers.llm, "llm", Fake())` ✅　`llm = Fake()` ❌ |

---

## 词 6 · SSE 帧格式

| 栏 | 内容 |
|---|---|
| 回答什么问题 | 客户端拿到一坨纯文本，怎么知道哪里是一段、哪里是下一段？ |
| 三条规矩 | ① 一行一个字段：`field: value`<br>② **空行 = 一帧结束**（唯一分隔符，没有 JSON、没有长度头、没有结束标签）<br>③ 常用字段：`data:`（正文）、`id:`（序号）、`event:`（类型，不写默认 `message`） |
| 项目位置 | `common/sse.py:31` `yield f"id: {idx}\ndata: {chunk}\n\n"`；`:32` 补 `event: end` 帧；`:34` `media_type="text/event-stream"` |
| 真实产物 | `b'id: 1\ndata: 你好\n\nid: 2\ndata: ，世界\n\nevent: end\ndata: done\n\n'` |
| ⚠️ 最经典的坑 | 末尾的 `\n\n`：**第 1 个 `\n` 结束 `data:` 这一行，第 2 个 `\n` 才是那个空行**。少写一个 → 这一帧永远挂着不显示 |
| ⚠️ 必须声明 | `media_type="text/event-stream"`，否则浏览器 `EventSource` 不认它是 SSE，当普通文本处理 |

---

## 词 7 · Last-Event-ID

| 栏 | 内容 |
|---|---|
| 回答什么问题 | 断线重连时，从哪一帧接着送？ |
| 谁写谁读 | **浏览器 `EventSource` 自动写**（它记着最后收到的 id）；**服务端读** |
| 项目位置 | `routers/llm.py:103-106`（`_resume_from`，默认 `"0"`）、`:131`（`min()` 夹紧）、`:133`（当 `start_id` 传下去） |
| ⚠️ 大小写 | HTTP 头名**大小写不敏感**——你发 `Last-Event-ID`，代码里读的是小写 `last-event-id`。这点必踩 |
| ⚠️ 为什么要 `min()` | 客户端可能报一个**超前**的数（它记的比服务端已生成的还多）。不夹紧 → 内容被跳过去 |
| 测试时怎么造 | `client.get("/llm/chat", params={...}, headers={"Last-Event-ID": "3"})` |
| ⚠️ 真续传 vs 恰好接上 | `/stream/greet` 无 id 无缓存 → **从头重放**；`/stream/counter` 带 id 但是**重算** → 内容换了就废；只有 `/llm/chat` 靠 `st.chunks` 缓存 → **真续传** |

---

## 词 8 · 怎么断言一个「流」

| 层 | 断言什么 | 判别力 |
|---|---|---|
| ① 状态码 / 头 | `status_code == 200`、`content-type` 是 `text/event-stream` | ⚠️ **零** |
| ② 帧内容 | `resp.text` 里有哪几帧、`id` 是否从 1 连续递增、最后一帧是否 `event: end` | 🟡 中 |
| ③ 行为 | 给 `Last-Event-ID: 3` → **只**出现第 4 块起，**且第 1-3 块不出现** | ✅ 强 |

**判别力的定义**：改动与不改动，断言结果不同。

- 零判别力例子：`assert resp.status_code == 200` —— 你把整个 `_frame` 删掉，它**照样通过**。这就是 39 个测试盖不到 `common/sse.py` 的根因。
- 有判别力例子：
  ```python
  assert "id: 1" not in resp.text   # 断点之前的不重发
  assert "id: 4" in resp.text       # 断点之后的补上了
  ```
  这条能分开「真续传」和「重算一遍恰好结果一样」。

---

## 复述清单（明天抽查，重点 3 和 6）

1. TestClient 在干嘛？为什么它是点亮 `_frame` 的唯一途径？
2. fixture 里 `yield` 上下两半分别是什么？默认 scope？
3. **`monkeypatch.setattr` 的第一个参数是什么？**（必问）
4. SSE 一帧怎么结束？为什么 f-string 末尾是 `\n\n`？
5. `Last-Event-ID` 是谁写的？`llm.py:131` 为什么要 `min()` 夹一下？
6. **什么样的断言才有判别力？举一个"零判别力"的例子。**（必问）

---

## 探针脚本（随时复跑）

| 脚本（`.workbuddy/tmp/`） | 证明什么 |
|---|---|
| `probe_lazy_sse.py` | 调用 vs 迭代；`_frame` 为什么一行没跑 |
| `probe_who_iterates.py` | 谁在迭代；迭代是一次性的 |
| `probe_async_vs_stream.py` | 异步买到的是"等的时候不占线程"，不是"能续传" |
| `probe_resume.py` | 重放 / 重算 / 真续传 三对照 |
| `probe_testclient.py` | 真服务器 vs TestClient，同一接口同一结果 |
| `probe_client_or_server.py` | 一条 print 证明服务端真跑了、`client.app is app` |
| `probe_which_layer_is_fake.py` | 逻辑层全走 vs 外面敲不到（端口不监听） |
| `probe_fixture_monkeypatch.py` | fixture 每测试一份 + monkeypatch 自动还原 |
