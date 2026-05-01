"""
异步 API 测试脚本
使用 httpx.AsyncClient + ASGI 直接测试
注意：httpx AsyncClient 默认不触发 lifespan，需手动初始化数据库
"""
import sys
import os
import asyncio

os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")

import httpx
from app.main import app
from app.core.database import init_db, AsyncSessionLocal
from app.services.menu_service import init_menu_data
from sqlalchemy import select
from app.models.user import User


async def setup():
    """手动执行数据库初始化和默认用户创建"""
    await init_db()
    async with AsyncSessionLocal() as db:
        await init_menu_data(db)
        result = await db.execute(select(User).where(User.id == 1))
        if result.scalar_one_or_none() is None:
            db.add(User(id=1, username="demo_user"))
            await db.commit()


async def test_root(client: httpx.AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    print("Root OK:", resp.json())


async def test_menu(client: httpx.AsyncClient):
    resp = await client.get("/api/v1/menu")
    assert resp.status_code == 200
    data = resp.json()
    print(f"Menu OK: {len(data)} items")
    assert len(data) >= 20


async def test_order(client: httpx.AsyncClient):
    payload = {
        "user_id": 1,
        "items": [
            {"menu_item_id": 1, "quantity": 1},
            {"menu_item_id": 2, "quantity": 2},
        ],
    }
    resp = await client.post("/api/v1/order", json=payload)
    assert resp.status_code == 200
    order = resp.json()
    print(f"Order OK: id={order['id']}, total={order['total_price']}, items={len(order['items'])}")
    assert order["total_price"] == 82.0

    resp2 = await client.get(f"/api/v1/order/{order['id']}")
    assert resp2.status_code == 200
    o2 = resp2.json()
    print(f"Query Order OK: status={o2['status']}")


async def test_chat_flow(client: httpx.AsyncClient):
    cart = []
    steps = [
        ("来一份宫保鸡丁", "order"),
        ("来一份麻婆豆腐x2", "order"),
        ("确认下单", "order"),
        ("查询我的订单", "query"),
        ("你好", "chat"),
    ]
    for msg, expected in steps:
        resp = await client.post("/api/v1/chat", json={"user_id": 1, "message": msg, "cart": cart})
        assert resp.status_code == 200
        result = resp.json()
        cart = result.get("cart", [])
        print(f"Chat '{msg}' => response_ok cart={cart}")


async def main():
    await setup()
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        await test_root(client)
        await test_menu(client)
        await test_order(client)
        await test_chat_flow(client)
    print("\n=== All tests passed! ===")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
