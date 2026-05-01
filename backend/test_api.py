"""
本地 API 测试脚本
使用 FastAPI TestClient 进行同步测试
"""
import sys
import os

# 设置假 key 确保能启动
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def safe_print(text):
    try:
        print(text)
    except UnicodeEncodeError:
        # Windows 控制台 gbk 编码问题，忽略无法编码的字符
        print(text.encode("gbk", "ignore").decode("gbk"))


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    safe_print(f"Root OK: {resp.json()}")


def test_menu():
    resp = client.get("/api/v1/menu")
    assert resp.status_code == 200
    data = resp.json()
    safe_print(f"Menu OK: {len(data)} items")
    assert len(data) >= 20


def test_order():
    payload = {
        "user_id": 1,
        "items": [
            {"menu_item_id": 1, "quantity": 1},
            {"menu_item_id": 2, "quantity": 2},
        ],
    }
    resp = client.post("/api/v1/order", json=payload)
    assert resp.status_code == 200
    order = resp.json()
    safe_print(f"Order OK: id={order['id']}, total={order['total_price']}, items={len(order['items'])}")
    assert order["total_price"] == 82.0

    resp2 = client.get(f"/api/v1/order/{order['id']}")
    assert resp2.status_code == 200
    o2 = resp2.json()
    safe_print(f"Query Order OK: status={o2['status']}")


def test_chat_flow():
    cart = []
    steps = [
        ("来一份宫保鸡丁", "order"),
        ("来一份麻婆豆腐x2", "order"),
        ("确认下单", "order"),
        ("查询我的订单", "query"),
        ("你好", "chat"),
    ]
    for msg, expected in steps:
        resp = client.post("/api/v1/chat", json={"user_id": 1, "message": msg, "cart": cart})
        assert resp.status_code == 200
        result = resp.json()
        cart = result.get("cart", [])
        safe_print(f"Chat '{msg}' => response_ok cart={cart}")


def main():
    test_root()
    test_menu()
    test_order()
    test_chat_flow()
    safe_print("\n=== All tests passed! ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
