# property_demo.py —— @property 最小可跑示例（day-031 参考材料）
#
# 目的：搞清三件事
#   1. 普通属性 vs @property，读的时候分别发生了什么
#   2. @property 如何"劫持"读取动作 → 实现「第一次读时才构建 + 缓存」
#   3. 为什么 property 名不能和背后存储名相同（无限递归）
#
# 直接跑：python property_demo.py


# ============ 对照组 A：普通属性 ============
class Plain:
    def __init__(self):
        print("  [Plain.__init__] 我在初始化时就建好了")
        self.value = "已构建的值"


# ============ 对照组 B：@property ============
class Lazy:
    def __init__(self):
        print("  [Lazy.__init__] 我只占个位，什么都没建")
        self.__value = None          # 背后存储：双下划线开头
        self.build_count = 0         # 记账用：构建了几次

    @property
    def value(self):
        print("  [Lazy.value] 有人读我了 → 执行这个函数")
        if self.__value is None:                 # 判据：没建过才建
            self.build_count += 1
            print("  [Lazy.value] 首次访问 → 现在才构建")
            self.__value = "已构建的值"
        return self.__value                      # 建过就直接给


def main():
    print("=" * 56)
    print("A. 普通属性：__init__ 里就构建好了")
    print("=" * 56)
    a = Plain()
    print("  读 a.value ->", a.value)
    print()

    print("=" * 56)
    print("B. @property：__init__ 只占位，读到才构建")
    print("=" * 56)
    b = Lazy()
    print("  刚创建完，build_count =", b.build_count)
    print("  --- 第一次读 ---")
    print("  读 b.value ->", b.value)
    print("  --- 第二次读 ---")
    print("  读 b.value ->", b.value)
    print()
    print("  关键结论：build_count =", b.build_count, "（构建只发生了 1 次 → 有缓存）")
    print()

    print("=" * 56)
    print("C. 验证「读 = 执行函数」")
    print("=" * 56)
    print("  打印 Box 类里的 value 是什么物体：")
    print("    Lazy.value          ->", Lazy.value)
    print("  （是个 property 对象，不是字符串 → 所以能拦截读取）")
    print("    Lazy.value.fget     ->", Lazy.value.fget)
    print()

    print("=" * 56)
    print("D. 反面教材：property 名 = 背后存储名 → 无限递归")
    print("=" * 56)

    class Bad:
        @property
        def x(self):
            return self.x        # 读 x 触发 x 的 getter，里面又读 x → 套娃

    try:
        Bad().x
    except RecursionError as e:
        print("  RecursionError（预期内）：", str(e)[:60])

    print()
    print("=" * 56)
    print("E. 只读属性写会怎样（保护数据用）")
    print("=" * 56)
    try:
        b.value = "手动改"
    except AttributeError as e:
        print("  AttributeError（预期内）：", e)


if __name__ == "__main__":
    main()
