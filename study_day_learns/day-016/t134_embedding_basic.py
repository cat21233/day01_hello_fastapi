from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[2]   # 项目根（脚本在 study_day_learns/day-016/ 下，向上 3 级）
import sys
sys.path.insert(0, str(ROOT))                # 保证 from config import settings 可用
load_dotenv(ROOT / ".env")
from openai import OpenAI
from config import settings

client = OpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url

)
resp = client.embeddings.create(
    model="deepseek-embed",
    input=["我喜欢吃苹果", "我喜欢吃水果", "汽车在公路上行驶"],
)
for d in resp.data:
    print(f"  句子 #{d.index}: 维度={len(d.embedding)}, 前5个={d.embedding[:5]}")
