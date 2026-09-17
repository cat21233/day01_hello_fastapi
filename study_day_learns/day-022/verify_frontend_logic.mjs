// 用 Node 22 的 web 标准 fetch / ReadableStream，跑一遍和 sse_test.html 里
// 完全相同的逻辑（帧解析 + 按 id 去重 + Last-Event-ID 续传）。
// 目的：在不开浏览器的情况下，先证明「前端逻辑」是对的。
// 跑法：node verify_frontend_logic.mjs [baseUrl]
const API = process.argv[2] || "http://127.0.0.1:8010";

let token = null;
let lastEventId = 0;
const seen = new Set();

async function login() {
  const resp = await fetch(`${API}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "zihao", password: "123456" }),
  });
  if (!resp.ok) throw new Error(`login HTTP ${resp.status}`);
  token = (await resp.json()).access_token;
  console.log(`登录成功，token 长度 ${token.length}`);
}

function handleFrame(frame) {
  let id = null, event = "message";
  const dataLines = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("id:")) id = parseInt(line.slice(3).trim(), 10);
    else if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
  }
  if (event === "end") return "end";
  if (id !== null) {
    if (seen.has(id)) return "dup";
    seen.add(id);
    lastEventId = Math.max(lastEventId, id);
  }
  return dataLines.join("\n");
}

async function connect({ resume = false, limit = 0, prompt, streamId }) {
  const headers = { Authorization: `Bearer ${token}` };
  if (resume) headers["Last-Event-ID"] = String(lastEventId);

  const url = `${API}/llm/chat?prompt=${encodeURIComponent(prompt)}&stream_id=${streamId}`;
  const controller = new AbortController();
  const resp = await fetch(url, { headers, signal: controller.signal });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let count = 0, dup = 0, firstDelay = null;
  const t0 = Date.now();

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let cut;
      while ((cut = buf.indexOf("\n\n")) >= 0) {
        const frame = buf.slice(0, cut);
        buf = buf.slice(cut + 2);
        const r = handleFrame(frame);
        if (r === "end") { console.log(`  [${((Date.now() - t0) / 1000).toFixed(2)}s] event: end`); return { count, dup, firstDelay }; }
        if (r === "dup") { dup++; continue; }
        if (firstDelay === null) firstDelay = (Date.now() - t0) / 1000;
        count++;
        if (limit && count >= limit) { controller.abort(); console.log("  （主动断开 = 模拟断网）"); return { count, dup, firstDelay }; }
      }
    }
  } catch (e) {
    if (e.name === "AbortError") return { count, dup, firstDelay };
    throw e;
  }
  return { count, dup, firstDelay };
}

const prompt = "请写一篇800字的作文，题目我的家乡，要求分段落，内容详细";

await login();
const streamId = Math.random().toString(36).slice(2, 10);
console.log(`stream_id = ${streamId}\n`);

console.log("== 第1次连接：收 5 帧后模拟断网 ==");
const a = await connect({ prompt, streamId, limit: 5 });
console.log(`  收到 ${a.count} 帧，最后 id=${lastEventId}`);

console.log("\n== 等 3 秒（后台继续生成） ==");
await new Promise((r) => setTimeout(r, 3000));

console.log("\n== 第2次连接：Last-Event-ID 续传 ==");
const b = await connect({ prompt, streamId, resume: true });

const ids = [...seen].sort((x, y) => x - y);
const contiguous = ids.every((v, i) => v === ids[0] + i);
console.log("\n== 结果 ==");
console.log(`  第1段 ${a.count} 帧，第2段 ${b.count} 帧，去重丢弃 ${b.dup} 帧`);
console.log(`  最终编号 ${ids[0]}..${ids[ids.length - 1]}，共 ${ids.length} 帧  ${contiguous ? "连续无缺失 ✅" : "有缺口 ❌"}`);
console.log(`  重连后首帧延迟 ${b.firstDelay.toFixed(2)}s（走缓存应 <0.3s）`);
