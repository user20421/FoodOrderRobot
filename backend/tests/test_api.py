"""
使用 TestClient 的 API 单元测试
无需启动独立服务器
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

from app.main import app
from app.core.database import get_db, Base
from app.core.mongodb import init_mongodb, close_mongodb

# 使用 SQLite 内存数据库做测试
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """创建测试数据库表"""
    import asyncio
    asyncio.run(_init_db())
    yield
    asyncio.run(_close_db())


async def _init_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_mongodb()


async def _close_db():
    await close_mongodb()
    await test_engine.dispose()


class TestHealth:
    def test_health_check(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"


class TestAuth:
    def test_register_and_login(self):
        import uuid
        test_uname = f"test_{uuid.uuid4().hex[:8]}"
        
        # 注册
        r = client.post("/api/v1/auth/register", json={
            "username": test_uname,
            "password": "123456",
            "phone": "13800138001"
        })
        assert r.status_code == 200, f"Register failed: {r.text}"
        
        # 登录
        r = client.post("/api/v1/auth/login", json={
            "username": test_uname,
            "password": "123456",
            "role": "customer"
        })
        assert r.status_code == 200, f"Login failed: {r.text}"
        data = r.json()
        assert data["user"]["username"] == test_uname
    
    def test_duplicate_register(self):
        import uuid
        test_uname = f"dup_{uuid.uuid4().hex[:8]}"
        
        client.post("/api/v1/auth/register", json={
            "username": test_uname,
            "password": "123456"
        })
        
        r = client.post("/api/v1/auth/register", json={
            "username": test_uname,
            "password": "123456"
        })
        assert r.status_code in (400, 422), f"Expected 400/422, got {r.status_code}"
    
    def test_wrong_password(self):
        import uuid
        test_uname = f"wp_{uuid.uuid4().hex[:8]}"
        
        client.post("/api/v1/auth/register", json={
            "username": test_uname,
            "password": "123456"
        })
        
        r = client.post("/api/v1/auth/login", json={
            "username": test_uname,
            "password": "wrongpwd"
        })
        assert r.status_code == 401


class TestMenu:
    def test_get_menu(self):
        r = client.get("/api/v1/menu")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        if len(items) > 0:
            item = items[0]
            assert all(k in item for k in ["id", "name", "price", "category", "stock"])


class TestSystem:
    def test_startup_time(self):
        r = client.get("/api/v1/system/startup")
        assert r.status_code == 200
        data = r.json()
        assert "startup_time" in data


class TestOrders:
    def test_order_flow(self):
        import uuid
        test_uname = f"order_{uuid.uuid4().hex[:8]}"
        
        # 注册
        r = client.post("/api/v1/auth/register", json={
            "username": test_uname,
            "password": "123456",
            "phone": "13800138002"
        })
        assert r.status_code == 200
        
        # 登录
        r = client.post("/api/v1/auth/login", json={
            "username": test_uname,
            "password": "123456"
        })
        user_id = r.json()["user"]["id"]
        
        # 获取菜单
        r = client.get("/api/v1/menu")
        items = r.json()
        if not items:
            pytest.skip("No menu items available")
        
        # 创建订单
        cart_items = [{
            "menu_item_id": items[0]["id"],
            "name": items[0]["name"],
            "quantity": 2,
            "unit_price": items[0]["price"]
        }]
        r = client.post("/api/v1/order", json={"items": cart_items},
            headers={"X-User-ID": str(user_id), "X-User-Role": "customer"})
        assert r.status_code == 200, f"Order create failed: {r.text}"
        order = r.json()
        assert "id" in order
        
        # 查询订单列表
        r = client.get("/api/v1/orders", headers={"X-User-ID": str(user_id), "X-User-Role": "customer"})
        assert r.status_code == 200
        orders = r.json()
        assert len(orders) >= 1
        
        # 查询订单详情
        r = client.get(f"/api/v1/order/{order['id']}", headers={"X-User-ID": str(user_id), "X-User-Role": "customer"})
        assert r.status_code == 200


class TestAdmin:
    def test_admin_menu_list(self):
        r = client.get("/api/v1/admin/menu", headers={"X-User-ID": "1", "X-User-Role": "admin"})
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
    
    def test_admin_orders_list(self):
        r = client.get("/api/v1/admin/orders", headers={"X-User-ID": "1", "X-User-Role": "admin"})
        assert r.status_code == 200
        orders = r.json()
        assert isinstance(orders, list)
    
    def test_admin_auth_reject(self):
        r = client.get("/api/v1/admin/menu", headers={"X-User-ID": "2", "X-User-Role": "customer"})
        assert r.status_code == 403
