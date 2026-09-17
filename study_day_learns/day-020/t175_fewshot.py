# day-020/t175_fewshot.py —— t-175 Zero-shot / Few-shot：在 prompt 中给示例
# 任务：用 few-shot 让模型把「用户问题」分类为 技术咨询 / 闲聊 / 投诉 三类
# 你只填下方 PROMPT（prompt 构造是今天要练的核心），其余已搭好，直接跑
#
# 运行：
#   cd C:\Users\yizihao\projects\day01-hello-fastapi
#   .\.venv\Scripts\python.exe study_day_learns\day-020\t175_fewshot.py
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))   # 必须在 import config 之前
load_dotenv(ROOT / ".env")
from openai import OpenAI
from config import settings

client = OpenAI(
    api_key=settings.agnes_api_key,
    base_url=settings.agnes_base_url,
)

# ════════════════ TODO：构造你的 few-shot prompt（今天的核心练习）════════════════
# 要求：
#   ① 一句指令：只输出类别名（技术咨询 / 闲聊 / 投诉），不要解释
#   ② 3 个示例，每个 = 一行「用户提问」+ 一行「分类：xxx」，三类各至少一个
#   ③ 新输入排在示例之后，格式与示例的「用户」行一致
#   ④ 用 ### 当分隔符（t-177 会专门练，今天先上手）
# 提示：示例要贴近真实分布、格式严格一致，模型才学得会「照着输出」
#
# 你之前写的 3 个示例输入（保留，直接复用）：
#   技术咨询: "关于jwt鉴权你觉得有哪些地方是值得学习的"
#   闲聊:     "你是谁"
#   投诉:     "你的响应速度也太慢了"
#
# ══ TODO：把上面 3 个输入 + 对应「分类：xxx」标签，连同【一句指令】和【一条新输入】，
#    全部拼成【一个字符串】写进 PROMPT。content 必须是单个字符串，不要写成 list！
PROMPT = """\
你是客服分类器，只输出类别名（技术咨询 / 闲聊 / 投诉），不要解释。

用户：关于jwt鉴权你觉得有哪些地方是值得学习的
分类：技术咨询
用户：你是谁
分类：闲聊
用户：你的响应速度也太慢了
分类：投诉

今天的天气不错啊

分类："""

# ═══════════════════════════════════════════════════════════════════════════════
resp = client.chat.completions.create(
    model=settings.agnes_model,
    messages=[{"role": "user", "content": PROMPT}],
    temperature=0,            # 分类任务要稳定，别让模型自由发挥
)
print("模型返回：", resp.choices[0].message.content.strip())
