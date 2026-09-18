"""这个文件里【一个测试函数都没有】，但文件名以 test_ 开头。

pytest 的收集规则（默认）：
    文件名匹配 test_*.py 或 *_test.py  ->  被当作测试文件  ->  import 它

而 import 一个文件 = 执行它顶层的每一行。

所以：顶层写的 print / 网络请求 / asyncio.run —— 都会在"收集阶段"被执行，
哪怕这个文件里 def test_ 一个都没有。

运行方式：
    cd C:/Users/yizihao/projects/day01-hello-fastapi
    python -m pytest study_day_learns/day-026/collect_demo/ -v -s

预期：屏幕上会出现下面这行 print，但测试结果是 "no tests ran"。
     —— 亲眼看到「收集 = import」。
"""

print(">>> [test_oops] pytest 一收集我，这行就执行了。而我没有任何 test 函数。")
