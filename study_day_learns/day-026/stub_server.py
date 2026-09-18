"""最小 stub 服务器：只为验证「环境不同 → 结果不同」。

它只做一件事：任何 GET 请求都回 200 + 合法 JSON。
（真项目里的 /slow-async、/slow-block 会 sleep，这个不 sleep，够用了。）

用途：起它之后，test_concurrency.py 顶层那次 HTTP 请求会成功，
      import 不再抛 JSONDecodeError —— 于是裸跑 pytest 就能跑通。

这证明：这个 bug 是「看环境脸色」的，不是稳定复现的。

启动：python study_day_learns/day-026/stub_server.py
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"ok": True, "path": self.path}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass          # 静音，别刷屏


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
