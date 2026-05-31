import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.llm import get_embedding

print("Testing Embedding...")
emb = get_embedding()
print(f"Embedding type: {type(emb).__name__}")

try:
    result = emb.embed_query("你好")
    print(f"Embedding dim: {len(result)}")
    print(f"First 5 values: {result[:5]}")
    print("EMBEDDING TEST PASSED")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
