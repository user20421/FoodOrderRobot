import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import time
from app.ai.llm import get_llm
from langchain_core.messages import HumanMessage

async def test():
    print("Testing LLM (ChatZhipuAI via langchain)...")
    llm = get_llm(temperature=0.1)
    print(f"LLM type: {type(llm).__name__}")

    t0 = time.time()
    try:
        r = await llm.ainvoke([HumanMessage(content="你好")])
        print(f"Time: {time.time() - t0:.2f}s")
        safe = r.content.encode("ascii", "replace").decode("ascii")
        print(f"Response: {safe[:100]}")
        print("LLM TEST PASSED")
    except Exception as e:
        print(f"Error after {time.time() - t0:.2f}s: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test())
