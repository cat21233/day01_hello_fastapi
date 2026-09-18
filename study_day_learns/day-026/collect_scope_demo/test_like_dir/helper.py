"""所在目录名是 test_like_dir —— 名字里明明有 "test"。

但我的文件名是 helper.py，不匹配 test_*.py 这个模式。

如果 "pytest 按目录名找测试" 成立，那我一定会被 import 并运行，
下面这个 assert 就会炸出来。

预期：我根本不会被收集，这句 assert 永远不会执行。
→ 再一次证明：只看【文件名】。
"""


def test_i_should_not_be_collected():
    raise AssertionError("如果我跑了，说明 pytest 真的在按目录名筛选")
