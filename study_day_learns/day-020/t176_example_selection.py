# day-020/t176_example_selection.py —— t-176 示例选择：挑选代表性 few-shot 样例
# t-175 你已会"把示例写进 prompt"。今天练：从候选池里挑哪几个当示例。
# 核心：示例质量 > 数量。要挑【覆盖各类 + 有区分度/边界】的，别挑雷同的。
#
# 运行：.\.venv\Scripts\python.exe study_day_learns\day-020\t176_example_selection.py
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

# 候选示例池（不用全用，挑代表性强的 3 个）
CANDIDATE_POOL = {
    "技术咨询": [
        "FastAPI 里 Depends 和 Query 有啥区别",
        "jwt 鉴权有哪些值得学的点",
        "怎么给接口加限流",
        "你们支持哪些大模型",
    ],
    "闲聊": [
        "你是谁",
        "今天天气不错啊",
        "哈哈哈太好笑了",
    ],
    "投诉": [
        "你们接口又 500 了到底什么时候修好",
        "响应速度也太慢了",
        "这文档写得也太烂了根本看不懂",
    ],
}

INSTRUCTION = "你是客服分类器，只输出类别名（技术咨询 / 闲聊 / 投诉），不要解释。"

# ══ TODO：从 CANDIDATE_POOL 三类里各挑 1 个（共 3 个）写进 EXAMPLES，每例两行 ══
# 提示：优先挑【能消除歧义/覆盖边界】的，别挑太雷同的。
EXAMPLES = """\
用户：FastAPI 里 Depends 和 Query 有啥区别
分类：技术咨询
用户：你是谁
分类：闲聊
用户：你们接口又 500 了到底什么时候修好
分类：投诉
"""

# 待分类的新输入（注意：这条有歧义——像投诉又像技术咨询，看你的示例能不能把它拽对）
TEST_QUERY = "你们接口文档里那个超时参数到底怎么配啊，配了三次都报错"

prompt = f"{INSTRUCTION}\n\n{EXAMPLES}\n\n用户：{TEST_QUERY}\n分类："

resp = client.chat.completions.create(
    model=settings.agnes_model,
    messages=[{"role": "user", "content": prompt}],
    temperature=0,            # 分类任务要稳定
)
print("模型返回：", resp.choices[0].message.content.strip())
