# -*- coding: utf-8 -*-
"""响应里找数据：给一个 JSON，按「字段名」或「值」搜出所有路径。

为什么需要它：
    爬虫/逆向最难的一步不是写代码，是「数据藏在响应里的哪一层」。
    浏览器里 Ctrl+F 只能帮你找到一个值，但深层嵌套的字段路径（data.list[0].sku.price）
    得靠眼睛数缩进。这个脚本把「找路径」变成一条命令，还顺手生成 Python 取值代码。

四种输入方式：
    python json_finder.py --url  http://127.0.0.1:8000/openapi.json --key securitySchemes
    python json_finder.py --file resp.json                          --value 23673
    python json_finder.py --file resp.json                          --key price --full
    Get-Clipboard | python json_finder.py --key lat        # 从剪贴板（DevTools Copy response 之后）

参数：
    --url / --file / 管道   三选一，不给就等 stdin
    --key     按字段名搜（匹配整条路径，所以父级容器名也能命中）
    --value   按值的子串搜（不确定字段名时最有效）
    --path    只在这个路径前缀下搜（缩小范围）
    --max     最多打印几条，默认 30
    --full    值不截断
"""

import argparse
import io
import json
import re
import sys
import urllib.parse
import urllib.request


def iter_leaves(obj, path=""):
    """深度遍历，产出 (路径, 叶子值)。空容器也算叶子，否则空列表会凭空消失。"""
    if isinstance(obj, dict):
        if not obj:
            yield path, obj
        for k, v in obj.items():
            yield from iter_leaves(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        if not obj:
            yield path, obj
        for i, v in enumerate(obj):
            # 空的 path 说明这是根列表，直接用 [i]，避免出现 "0.address" 这种裸数字
            yield from iter_leaves(v, f"{path}[{i}]" if path else f"[{i}]")
    else:
        yield path, obj


def to_python_expr(path, root="data"):
    """把 "data.list[0].price" 这种路径转成可直接粘贴的 data["data"]["list"][0]["price"]"""
    expr = root
    for m in re.finditer(r"([^\.\[\]]+)|\[(\d+)\]", path):
        expr += f"[{m.group(2)}]" if m.group(2) is not None else f'["{m.group(1)}"]'
    return expr


def find(data, key=None, value=None, prefix=None):
    hits = []
    for path, val in iter_leaves(data):
        if prefix and not path.startswith(prefix):
            continue
        why = []
        if key and key.lower() in path.lower():
            why.append(f"字段名含 {key}")
        if value and value in str(val):
            why.append(f"值含 {value}")
        if why:
            hits.append((path, val, " / ".join(why)))
    return hits


def load(args):
    if args.url:
        # 本机地址必须绕过代理：代理环境下 HTTP_PROXY 会把 127.0.0.1 也转发出去 → 502
        host = urllib.parse.urlsplit(args.url).hostname
        if host in ("127.0.0.1", "localhost", "::1"):
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        else:
            opener = urllib.request.build_opener()
        req = urllib.request.Request(args.url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", "replace")
    elif args.file:
        raw = io.open(args.file, encoding="utf-8", errors="replace").read()
    else:
        raw = sys.stdin.read()
    if not raw.strip():
        sys.exit("没读到内容：--url/--file/管道 至少给一个")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        # 逆向里最常见的就是响应不是干净 JSON（JSONP 外壳 / 前面混了日志）
        head = raw.strip()[:120].replace("\n", " ")
        sys.exit(f"不是合法 JSON：{exc}\n开头是：{head}\n"
                 f"提示：JSONP 要剥掉 callback(...) 外壳；HTML 响应请改用 xpath/bs4")


def main():
    p = argparse.ArgumentParser(description="在 JSON 响应里按字段名或值搜路径")
    p.add_argument("--url")
    p.add_argument("--file")
    p.add_argument("--key", help="字段名关键词（子串匹配整条路径）")
    p.add_argument("--value", help="值的子串")
    p.add_argument("--path", help="只搜这个路径前缀")
    p.add_argument("--max", type=int, default=30)
    p.add_argument("--full", action="store_true", help="值不截断")
    args = p.parse_args()

    if not args.key and not args.value:
        sys.exit("至少给 --key 或 --value 之一")

    data = load(args)
    hits = find(data, args.key, args.value, args.path)

    if not hits:
        print("没匹配到。换一个更独特的子串试试：")
        print("  价格/ID 用数字，标题取中间连续的几个字，别用 'name' 这种烂大街的字段名")
        return

    print(f"命中 {len(hits)} 处" + (f"，只显示前 {args.max} 处" if len(hits) > args.max else "") + "：\n")
    for path, val, why in hits[:args.max]:
        s = str(val)
        if not args.full and len(s) > 60:
            s = s[:57] + "..."
        print(f"  {path}")
        print(f"      = {s}")
        print(f"      [{why}]")

    print("\nPython 取值写法（可直接粘）：")
    for path, _, _ in hits[:3]:
        print(f"  {to_python_expr(path)}")


if __name__ == "__main__":
    main()
