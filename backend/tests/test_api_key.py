import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings

api_key = settings.zhipu_api_key or os.environ.get("ZHIPU_API_KEY", "")
print(f"API Key from env: {api_key[:20]}..." if api_key else "No API Key")
print(f"Chat model: {settings.chat_model}")

# 测试智谱对话模型
try:
    from zhipuai import ZhipuAI
    client = ZhipuAI(api_key=api_key)

    print(f"\nTesting {settings.chat_model}...")
    response = client.chat.completions.create(
        model=settings.chat_model,
        messages=[{"role": "user", "content": "你好"}],
    )
    content = response.choices[0].message.content[:100]
    safe = content.encode("ascii", "replace").decode("ascii")
    print(f"response: {safe}")
    print(f"{settings.chat_model}: OK")
except Exception as e:
    print(f"{settings.chat_model} ERROR: {type(e).__name__}: {e}")
