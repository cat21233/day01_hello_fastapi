"""所在目录名是 not_test_dir —— 里面压根没有 "test" 这个词。

如果 "pytest 会先去找名字带 test 的目录" 这个说法成立，
那这个文件就不该被收集到。

预期：它照样被收集、照样运行通过。
→ 证明筛选依据是【文件名】，不是【目录名】。
"""


def test_i_am_collected_anyway():
    print("    >>> [not_test_dir/test_hit.py] 我被收集了，尽管目录名里没有 test")
    assert True
