# 【正面教材】有 __main__ 守卫
#
# 和 bad_module.py 唯一的差别：asyncio.run(main()) 被包进了 if 里。
# __name__ 这个变量由 Python 自动设置：
#   - 直接运行这个文件  -> __name__ == "__main__"  -> 条件成立 -> 执行
#   - 被别的文件 import -> __name__ == "good_module"（模块名）-> 条件不成立 -> 跳过

import asyncio


async def main():
    print("    >>> [good_module] main() 里的业务逻辑跑了！")


if __name__ == "__main__":
    asyncio.run(main())
