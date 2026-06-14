"""
全面功能测试脚本
测试所有API端点和核心功能
"""
import asyncio
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
import pytest

pytestmark = pytest.mark.asyncio

BASE_URL = "http://127.0.0.1:8000"
API = f"{BASE_URL}/api/v1"
TIMEOUT = 60.0  # LLM 调用可能需要较长时间

results = []

def report(name, success, detail=""):
    status = "[PASS]" if success else "[FAIL]"
    results.append(f"{status} | {name} {detail}")
    print(f"{status} | {name} {detail}")
    return success

async def test_health():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(f"{BASE_URL}/health")
        report("Health Check", r.status_code == 200, f"status={r.json().get('status')}")

async def test_auth():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        import uuid
        test_uname = f"testuser_{uuid.uuid4().hex[:8]}"
        # 注册新用户
        r = await client.post(f"{API}/auth/register", json={
            "username": test_uname,
            "password": "123456",
            "phone": "13800138001"
        })
        reg_ok = r.status_code == 200
        report("Auth Register", reg_ok, f"code={r.status_code}")
        
        # 登录
        r = await client.post(f"{API}/auth/login", json={
            "username": test_uname,
            "password": "123456",
            "role": "customer"
        })
        login_ok = r.status_code == 200
        data = r.json()
        report("Auth Login", login_ok, f"user={data.get('user',{}).get('username')}, msg={data.get('message')}")
        
        # 重复注册应该失败
        r = await client.post(f"{API}/auth/register", json={
            "username": test_uname,
            "password": "123456"
        })
        dup_ok = r.status_code in (400, 422)
        report("Auth Duplicate", dup_ok, f"code={r.status_code}")
        
        # 错误密码登录应该失败
        r = await client.post(f"{API}/auth/login", json={
            "username": test_uname,
            "password": "wrongpwd"
        })
        wrong_ok = r.status_code == 401
        report("Auth Wrong Pwd", wrong_ok, f"code={r.status_code}")

async def test_menu():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(f"{API}/menu")
        ok = r.status_code == 200
        items = r.json()
        report("Menu API", ok, f"items={len(items)}")
        
        if ok and len(items) > 0:
            item = items[0]
            report("Menu Item Structure",
                   all(k in item for k in ["id", "name", "price", "category", "stock"]),
                   f"name={item.get('name')}")

async def test_chat():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # 测试问候语
        r = await client.post(f"{API}/chat", json={
            "user_id": 999,
            "message": "你好",
            "cart": []
        })
        ok = r.status_code == 200
        data = r.json()
        report("Chat Greeting", ok, f"response_len={len(data.get('response',''))}")
        
        # 测试点餐意图
        r = await client.post(f"{API}/chat", json={
            "user_id": 999,
            "message": "来一份宫保鸡丁",
            "cart": []
        })
        ok = r.status_code == 200
        data = r.json()
        report("Chat Order Intent", ok, f"cart_len={len(data.get('cart',[]))}")
        
        # 测试咨询意图
        r = await client.post(f"{API}/chat", json={
            "user_id": 999,
            "message": "你们有什么招牌菜",
            "cart": []
        })
        ok = r.status_code == 200
        report("Chat Inquiry Intent", ok)
        
        # 测试推荐意图
        r = await client.post(f"{API}/chat", json={
            "user_id": 999,
            "message": "推荐几个下饭菜",
            "cart": []
        })
        ok = r.status_code == 200
        report("Chat Recommend Intent", ok)

async def test_orders():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        import uuid
        test_uname = f"orderuser_{uuid.uuid4().hex[:8]}"
        # 先注册一个测试用户
        r = await client.post(f"{API}/auth/register", json={
            "username": test_uname,
            "password": "123456",
            "phone": "13800138002"
        })
        if r.status_code not in (200, 400):
            report("Order Create", False, f"Register failed: {r.status_code}")
            report("Order List", False, "Skipped")
            report("Order Detail", False, "Skipped")
            report("Order Export", False, "Skipped")
            return
        
        # 登录获取用户
        r = await client.post(f"{API}/auth/login", json={
            "username": test_uname,
            "password": "123456"
        })
        user = r.json().get("user", {})
        user_id = user.get("id")
        
        # 获取菜单用于下单
        r = await client.get(f"{API}/menu")
        items = r.json()
        if not items:
            report("Order Create", False, "No menu items")
            return
        
        # 创建订单
        cart_items = [{
            "menu_item_id": items[0]["id"],
            "name": items[0]["name"],
            "quantity": 2,
            "unit_price": items[0]["price"]
        }]
        r = await client.post(f"{API}/order", 
            json={"items": cart_items},
            headers={"X-User-ID": str(user_id), "X-User-Role": "customer"}
        )
        ok = r.status_code == 200
        order = r.json()
        report("Order Create", ok, f"order_id={order.get('id')}, total={order.get('total_price')}")
        
        if ok:
            order_id = order.get("id")
            
            # 查询订单列表
            r = await client.get(f"{API}/orders",
                headers={"X-User-ID": str(user_id), "X-User-Role": "customer"}
            )
            list_ok = r.status_code == 200
            orders = r.json()
            report("Order List", list_ok, f"count={len(orders)}")
            
            # 查询订单详情
            r = await client.get(f"{API}/order/{order_id}",
                headers={"X-User-ID": str(user_id), "X-User-Role": "customer"}
            )
            detail_ok = r.status_code == 200
            report("Order Detail", detail_ok)
            
            # 导出订单
            r = await client.get(f"{API}/orders/{order_id}/export",
                headers={"X-User-ID": str(user_id), "X-User-Role": "customer"}
            )
            export_ok = r.status_code == 200
            report("Order Export", export_ok, f"len={len(r.text)}")

async def test_admin():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # 登录admin
        r = await client.post(f"{API}/auth/login", json={
            "username": "admin",
            "password": "123456",
            "role": "admin"
        })
        
        # 商家获取菜单
        r = await client.get(f"{API}/admin/menu",
            headers={"X-User-ID": "1", "X-User-Role": "admin"}
        )
        ok = r.status_code == 200
        items = r.json()
        report("Admin Menu List", ok, f"count={len(items)}")
        
        # 商家获取订单
        r = await client.get(f"{API}/admin/orders",
            headers={"X-User-ID": "1", "X-User-Role": "admin"}
        )
        ok = r.status_code == 200
        orders = r.json()
        report("Admin Orders", ok, f"count={len(orders)}")
        
        # 非admin访问应该被拒绝
        r = await client.get(f"{API}/admin/menu",
            headers={"X-User-ID": "2", "X-User-Role": "customer"}
        )
        forbid_ok = r.status_code == 403
        report("Admin Auth Reject", forbid_ok, f"code={r.status_code}")

async def test_system():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(f"{API}/system/startup")
        ok = r.status_code == 200
        data = r.json()
        report("System Startup", ok, f"time={data.get('startup_time','')[:19]}")

async def test_image_search():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # 创建一个假的图片文件
        from io import BytesIO
        files = {"file": ("test.jpg", BytesIO(b"fake_image_data"), "image/jpeg")}
        r = await client.post(f"{API}/image/search", files=files)
        ok = r.status_code == 200
        data = r.json()
        report("Image Search", ok, f"has_response={'response' in data}")

async def run_all_tests():
    print("=" * 60)
    print("智能点餐机器人 - 全面功能测试")
    print("=" * 60)
    
    await test_health()
    await test_system()
    await test_auth()
    await test_menu()
    await test_chat()
    await test_orders()
    await test_admin()
    await test_image_search()
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    passed = sum(1 for r in results if "[PASS]" in r)
    failed = sum(1 for r in results if "[FAIL]" in r)
    for r in results:
        print(r)
    print(f"\n总计: {passed} 通过, {failed} 失败")
    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
