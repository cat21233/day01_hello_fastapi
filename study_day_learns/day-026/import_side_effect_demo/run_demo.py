"""判别性实验：import 一个模块时，到底会执行哪些行？

本脚本只做一件事：import 两个模块，然后观察谁"自己动起来了"。

预期结果（这就是判别力所在）：
    import bad_module  -> 会看到它的 main() 业务逻辑被打印出来  ← 出事了
    import good_module -> 什么都不打印                        ← 正常

如果两者表现一样，说明这个实验没有判别力，我的说法就是错的。

运行：
    cd C:/Users/yizihao/projects/day01-hello-fastapi
    python study_day_learns/day-026/import_side_effect_demo/run_demo.py
"""

import pathlib
import sys

# 让 Python 能找到同目录下的 bad_module / good_module
sys.path.insert(0, str(pathlib.Path(__file__).parent))

line = "=" * 62

print(line)
print("实验开始。注意：下面这段代码里，我【只写了 import】，没有调用任何人。")
print(line)

print()
print("[第 1 步] import bad_module  （顶层裸调用 asyncio.run）")
import bad_module          # noqa: E402

print()
print("[第 2 步] import good_module （asyncio.run 在 __main__ 守卫里）")
import good_module         # noqa: E402

print()
print(line)
print("结论：bad_module 的 main() 在 import 时自己跑了；good_module 没有。")
print("      → 「import 一个模块」= 从上到下执行它顶层的每一行代码。")
print(line)
