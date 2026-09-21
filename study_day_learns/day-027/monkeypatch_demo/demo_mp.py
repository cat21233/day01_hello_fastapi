"""day-027 实验：monkeypatch 到底做了什么？

一句话结论：
    monkeypatch.setattr(obj, "attr", value)   ≈   obj.attr = value
    区别只有一条 —— 测试跑完，pytest 自动帮你「撤销这一次替换」。

注意：撤销的是「setattr 那一刻的旧值」，不是「模块原始的出厂值」。
      所以它救不了上一个测试造成的污染。

运行（文件名故意不叫 test_*.py，避免污染裸跑 pytest 的收集范围；
显式指定路径时 pytest 会跳过文件名匹配规则）：
    pytest study_day_learns/day-027/monkeypatch_demo/demo_mp.py -s -q
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]     # day-027 -> study_day_learns -> 项目根
sys.path.insert(0, str(ROOT))                   # 必须在 import 根模块【之前】（坑 #12）

import routers.llm as rl  # noqa: E402

rl._DEMO_A = "原始"      # 用于演示「手动赋值」
rl._DEMO_B = "原始"      # 用于演示「monkeypatch」


def test_1_初始值():
    print(f"\n[1] _DEMO_A={rl._DEMO_A}  _DEMO_B={rl._DEMO_B}")


def test_2_手动赋值_A():
    rl._DEMO_A = "被改过"
    print(f"[2] 手动赋值后  _DEMO_A={rl._DEMO_A}")


def test_3_A有没有被还原():
    print(f"[3] 下一个测试  _DEMO_A={rl._DEMO_A}   <-- 还是'被改过' = 污染 ✗")


def test_4_monkeypatch替换_B(monkeypatch):
    monkeypatch.setattr(rl, "_DEMO_B", "被改过")
    print(f"[4] monkeypatch _DEMO_B={rl._DEMO_B}")


def test_5_B有没有被还原():
    print(f"[5] 下一个测试  _DEMO_B={rl._DEMO_B}   <-- 回到'原始' = 自动撤销 ✓")


def test_6_先手动污染A再monkeypatch(monkeypatch):
    rl._DEMO_A = "污染过"
    monkeypatch.setattr(rl, "_DEMO_A", "又被改过")
    print(f"[6] _DEMO_A 现在是 {rl._DEMO_A}（monkeypatch 记下的旧值 = '污染过'）")


def test_7_撤销到污染值而不是原始值():
    print(f"[7] 下一个测试  _DEMO_A={rl._DEMO_A}   <-- 是'污染过'，不是'原始' ->")
    print("    monkeypatch 只负责撤销它自己那一次替换，管不了别人留下的烂摊子")
