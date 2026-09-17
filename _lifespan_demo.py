"""临时验证脚本：证明 lifespan（启动校验）只在 `with TestClient(app)` 时触发。

跑完可删。用法：
    python _lifespan_demo.py
"""
from fastapi.testclient import TestClient

from main import app
import config

# 注意：必须在 `from main import app` 之后再改！
# routers/llm.py 在模块导入时就执行了 LLMClient(settings.llm_provider)，
# 提前改成未知厂商会在 import 阶段直接 ValueError，轮不到校验出场。
# 改在这里也有效：validate_settings() 是「调用时」才读 settings.llm_provider。
config.settings.llm_provider = "openai"

print("配置状态: llm_provider = openai（.env 里没配 openai 的 key）")
print("         configured_providers() =", config.configured_providers())
print()

print("---- 1) 不带 with ----")
c = TestClient(app)
print("   /health ->", c.get("/health").status_code)
print()

print("---- 2) 带 with ----")
try:
    with TestClient(app) as c2:
        print("   /health ->", c2.get("/health").status_code)
except Exception as e:
    print("   启动即炸 ->", type(e).__name__, ":", e)
