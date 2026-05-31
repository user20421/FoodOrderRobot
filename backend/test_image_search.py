"""
图片搜索接口测试脚本
用法: .venv\Scripts\python test_image_search.py <图片路径>
"""
import sys
import requests

API_BASE = "http://127.0.0.1:8000/api/v1"


def test_image_search(image_path: str):
    url = f"{API_BASE}/image/search"
    with open(image_path, "rb") as f:
        files = {"file": (image_path, f, "image/jpeg")}
        resp = requests.post(url, files=files, timeout=60)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_image_search.py <图片路径>")
        sys.exit(1)
    test_image_search(sys.argv[1])
