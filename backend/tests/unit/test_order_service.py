"""
订单服务单元测试
使用 SQLite 内存数据库验证核心下单逻辑与事务一致性。
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.database import Base
from app.models.user import User
from app.models.menu import MenuCategory, MenuItem
from app.models.order import Order, OrderItem
from app.services.order_service import create_order
from app.schemas.order import CartItem
from app.core.exceptions import BusinessException

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="function")
async def db():
    """每个测试用例使用独立的内存数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def sample_data(db: AsyncSession):
    """准备测试数据：用户 + 菜品"""
    user = User(username="test_user", password="", role="customer")
    db.add(user)
    await db.flush()

    category = MenuCategory(name="热菜", sort_order=1)
    db.add(category)
    await db.flush()

    dish = MenuItem(
        name="宫保鸡丁",
        price=38.0,
        category="热菜",
        stock=10,
        is_recommended=1,
        sales_count=0,
    )
    db.add(dish)
    await db.commit()

    return {"user": user, "dish": dish}


async def test_create_order_success(db: AsyncSession, sample_data):
    """正常下单应扣减库存、增加销量"""
    user = sample_data["user"]
    dish = sample_data["dish"]

    items = [CartItem(menu_item_id=dish.id, name=dish.name, quantity=2, unit_price=dish.price)]
    order = await create_order(db, user.id, items)

    assert order.user_id == user.id
    assert order.total_price == 76.0
    assert len(order.items) == 1
    assert order.items[0].quantity == 2

    # 验证库存扣减和销量增加
    await db.refresh(dish)
    assert dish.stock == 8
    assert dish.sales_count == 2


async def test_create_order_insufficient_stock(db: AsyncSession, sample_data):
    """库存不足时应抛出业务异常"""
    user = sample_data["user"]
    dish = sample_data["dish"]

    items = [CartItem(menu_item_id=dish.id, name=dish.name, quantity=100, unit_price=dish.price)]
    with pytest.raises(BusinessException):
        await create_order(db, user.id, items)

    # 验证库存未被扣减
    await db.refresh(dish)
    assert dish.stock == 10
