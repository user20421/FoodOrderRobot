import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings

print(f"API Key from env: {settings.dashscope_api_key[:20]}..." if settings.dashscope_api_key else "No API Key")
print(f"Chat model: {settings.chat_model}")

# 测试 qwen-turbo
try:
    import dashscope
    dashscope.api_key = settings.dashscope_api_key
    from http import HTTPStatus
    from dashscope import Generation
    
    print("\nTesting qwen-turbo...")
    response = Generation.call(
        model="qwen-turbo",
        messages=[{"role": "user", "content": "你好"}],
        result_format="message"
    )
    print(f"status: {response.status_code}")
    if response.status_code == HTTPStatus.OK:
        print("qwen-turbo: OK")
    else:
        print(f"qwen-turbo error: {response.message}")
        
except Exception as e:
    print(f"qwen-turbo ERROR: {type(e).__name__}: {e}")

# 测试 qwen-plus
try:
    print("\nTesting qwen-plus...")
    response = Generation.call(
        model="qwen-plus",
        messages=[{"role": "user", "content": "你好"}],
        result_format="message"
    )
    print(f"status: {response.status_code}")
    if response.status_code == HTTPStatus.OK:
        print("qwen-plus: OK")
    else:
        print(f"qwen-plus error: {response.message}")
        
except Exception as e:
    print(f"qwen-plus ERROR: {type(e).__name__}: {e}")
