# 【反面教材】没有 __main__ 守卫
#
# 关键：第 12 行的 asyncio.run(main()) 是「裸」在模块顶层的。
# 它不属于任何函数、不属于任何 if —— 所以只要这个文件被 import，
# Python 从上到下执行时就会撞到它，然后跑起来。

import asyncio


async def main():
    print("    >>> [bad_module] main() 里的业务逻辑跑了！")


asyncio.run(main())      # ← 顶层裸调用：import 即执行
