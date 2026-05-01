# 智能点餐机器人

基于 **FastAPI + Vue3 + 多智能体架构** 的智能点餐系统，支持顾客端对话点餐和商家端后台管理。

## 核心架构：多智能体（Multi-Agent）

本系统采用 **Supervisor + 5 个业务智能体** 的多智能体协作架构，每个智能体负责一个独立的业务领域：

```
                              用户消息
                                 |
                                 v
                    +-------------------------+
                    |      Supervisor         |
                    |   （调度中心 - 只做路由）  |
                    +-----------+-------------+
                                |
          +---------+----------+----------+----------+
          |         |          |          |          |
          v         v          v          v          v
   Recommender  Inquiry     Order    OrderTracking  Customer
      Agent      Agent      Agent       Agent      Service
        |          |          |            |          |
   +----+----+  +--+---+  +---+----+  +----+----+  +---+----+
   |menu_tools|  |menu_ |  |order_ |  |order_  |  |system_ |
   |rag_tools |  |tools |  |tools |  |tools  |  |tools  |
   +---------+  +------+  +------+  +--------+  +--------+
```

| 智能体 | 名称 | 职责 | 核心场景 |
|---|---|---|---|
| **Supervisor** | 调度中心 | 意图分类 + 路由分发 | 接收用户消息，判断属于哪个业务场景 |
| **RecommenderAgent** | 推荐专员 | 根据偏好推荐菜品 | "有什么好吃的？" "推荐下饭菜" |
| **InquiryAgent** | 问询专员 | 回答具体信息查询 | "宫保鸡丁多少钱？" "有鱼香肉丝吗？" "营业到几点？" |
| **OrderAgent** | 点餐专员 | 解析点餐、管理购物车、确认下单 | "来一份宫保鸡丁" "确认下单" |
| **OrderTrackingAgent** | 订单追踪专员 | 查询订单历史和状态 | "我点了什么？" "查订单" |
| **CustomerServiceAgent** | 客服专员 | 闲聊、问候、兜底回复 | "你好" "谢谢" "再见" |

### 架构设计原则

1. **单一职责**：每个 Agent 只负责一类业务场景，不跨界
2. **工具专属**：每个 Agent 拥有专属的工具集，工具按领域拆分（menu/order/system/parser）
3. **调度与业务分离**：Supervisor 只做意图路由，不处理任何业务逻辑
4. **降级运行**：无 DashScope API Key 时，系统通过关键词 fallback 完整运行

### 调度方式

1. **LLM 智能调度**（有 DashScope API Key 时）：使用 `qwen-plus` 进行意图分类
2. **关键词 Fallback**（无 API Key 时）：通过关键词匹配实现意图分类
3. **前置规则**：询问具体菜品（"有宫保鸡丁吗"）优先走 InquiryAgent 而非 OrderAgent

## 功能特性

### 顾客端
- **智能点餐对话**：多轮对话，支持自然语言点餐（"来2份宫保鸡丁"）
- **菜单浏览**：分类展示，实时显示库存，库存为0显示"已售罄"
- **购物车**：独立页面，支持增删改数量、一键下单
- **订单查询**：查看历史订单及明细
- **用户隔离**：每个用户独立的聊天记录、购物车、订单

### 商家端
- **商品管理**：增删改查菜品，实时调整库存和价格
- **订单管理**：查看所有顾客订单及菜品明细
- **库存同步**：商家改库存后顾客端即时可见，顾客下单自动扣减库存

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | FastAPI + SQLAlchemy 2.0 + MySQL |
| AI 引擎 | LangChain + DashScope (qwen-plus) + 多智能体架构 |
| 向量检索 | Chroma + DashScope Embedding |
| 前端 | Vue 3 + Vite + Element Plus + Pinia |
| 数据库 | MySQL 8.0 |

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+
- MySQL 8.0（账号：root / 123456，数据库：ordering_bot）
- DashScope API Key（可选，无 Key 时降级为数据库查询模式）

### 安装依赖

```bash
# 后端
pip install -r backend/requirements.txt

# 前端
cd frontend
npm install
```

### 一键启动

```bash
python start.py
```

启动后访问：
- 顾客端：http://localhost:5173
- 后端文档：http://127.0.0.1:8000/docs

### 登录账号

| 角色 | 用户名 | 密码 |
|---|---|---|
| 商家 | admin | 123456 |
| 顾客 | 自行注册 | - |

## API 接口

### 认证
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/v1/auth/register | 顾客注册 |
| POST | /api/v1/auth/login | 登录（支持角色选择） |

### 顾客端
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/v1/chat | 智能点餐对话（Supervisor 调度） |
| GET | /api/v1/menu | 获取菜单（含库存） |
| GET | /api/v1/orders | 查询我的订单 |

### 商家端
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/v1/admin/menu | 获取商品列表 |
| POST | /api/v1/admin/menu | 新增商品 |
| PUT | /api/v1/admin/menu/{id} | 修改商品 |
| DELETE | /api/v1/admin/menu/{id} | 删除商品 |
| GET | /api/v1/admin/orders | 查看所有订单 |

## 项目结构

```
点餐机器人/
├── backend/
│   ├── app/
│   │   ├── ai/                    # AI 核心层
│   │   │   ├── agents/            # 业务智能体
│   │   │   │   ├── base.py        # Agent 基类
│   │   │   │   ├── recommender.py # 推荐智能体
│   │   │   │   ├── inquiry.py     # 问询智能体
│   │   │   │   ├── order.py       # 点餐智能体
│   │   │   │   ├── order_tracking.py  # 订单追踪智能体
│   │   │   │   └── customer_service.py # 客服智能体
│   │   │   ├── tools/             # 领域工具层
│   │   │   │   ├── menu_tools.py  # 菜单查询/搜索/格式化
│   │   │   │   ├── order_tools.py # 购物车/订单操作
│   │   │   │   ├── system_tools.py # 店铺信息（营业时间等）
│   │   │   │   └── parser_tools.py # 自然语言解析（数量/偏好提取）
│   │   │   ├── supervisor.py      # Supervisor 调度中心
│   │   │   └── rag.py             # RAG 向量检索
│   │   ├── api/v1/                # API 路由
│   │   ├── core/                  # 配置、数据库
│   │   ├── models/                # ORM 模型
│   │   ├── repositories/          # 数据访问层
│   │   ├── schemas/               # Pydantic Schema
│   │   ├── services/              # 业务逻辑层
│   │   └── main.py                # FastAPI 入口
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── views/                 # 页面组件
│       │   ├── ChatView.vue       # 智能点餐
│       │   ├── MenuView.vue       # 菜单浏览
│       │   ├── CartView.vue       # 购物车
│       │   ├── OrdersView.vue     # 我的订单
│       │   ├── LoginView.vue      # 登录/注册
│       │   └── admin/             # 商家后台
│       ├── stores/                # Pinia 状态管理
│       ├── router/                # 路由配置
│       └── api/                   # API 封装
└── start.py                       # 一键启动脚本
```

## 智能体详细设计

### RecommenderAgent（推荐专员）

```python
# 职责
根据用户口味偏好、场景需求、饮食限制，从菜单中筛选并推荐菜品。

# 适用场景
- "有什么好吃的？"
- "推荐几个下饭菜"
- "我想吃点清淡的"
- "适合小孩吃的有什么？"

# 核心工具
- search_by_preference(spicy_level, categories, tags, dietary) -> List[MenuItem]
- get_signature_dishes(limit=5) -> List[MenuItem]
- rag_retrieve(query, k=3) -> str
- format_dish_list(dishes, title) -> str

# 流程
1. extract_preferences(message) 提取用户偏好
2. search_by_preference() 从数据库筛选候选
3. 尝试 LLM 润色（带菜品名校验防幻觉）
4. Fallback：直接返回数据库筛选结果
```

### InquiryAgent（问询专员）

```python
# 职责
精确回答用户的信息查询，包括菜品详情、菜单、价格、库存、营业时间、配送等。

# 适用场景
- "宫保鸡丁多少钱？"
- "有鱼香肉丝吗？"
- "你们营业到几点？"
- "有什么菜单？"

# 核心工具
- get_dish_detail(dish_name) -> dict
- search_dishes_by_name(keyword) -> List[MenuItem]
- get_full_menu_text() -> str
- get_system_info(info_type) -> str
- check_stock(dish_name) -> int
- detect_info_intent(message) -> str | None

# 流程
1. 判断信息类型（菜单/系统信息/菜品详情/库存）
2. 调用对应工具获取精确信息
3. 直接回答，不啰嗦
```

### OrderAgent（点餐专员）

```python
# 职责
解析用户点餐意图，管理购物车，确认时创建订单并扣减库存。

# 适用场景
- "来一份宫保鸡丁"
- "再加个麻婆豆腐"
- "确认下单"
- "购物车有什么？"

# 核心工具
- extract_dish_names(message, menu_items) -> List[CartItem]
- merge_cart(existing, new_items) -> List[CartItem]
- get_cart_summary(cart) -> str
- validate_cart_stock(cart) -> ValidationResult
- submit_order(user_id, cart) -> OrderResult

# 流程
1. 判断是"确认下单"还是"查看购物车"还是"加购"
2. 若是加购：extract_dish_names -> merge_cart -> 返回购物车摘要
3. 若是确认：validate_cart_stock -> submit_order -> 返回订单详情
4. 若是查看：get_cart_summary -> 返回当前购物车
```

### OrderTrackingAgent（订单追踪专员）

```python
# 职责
查询用户的历史订单记录和订单详情。

# 适用场景
- "我点了什么？"
- "查询我的订单"
- "最新订单详情"

# 核心工具
- get_user_orders(user_id, limit=10) -> List[Order]
- get_order_detail(order_id) -> dict
- get_latest_order(user_id) -> dict | None
- format_order_list(orders) -> str
- format_order_detail(order) -> str

# 流程
1. 判断是查列表还是查详情
2. 调用对应工具查询
3. 格式化返回
```

### CustomerServiceAgent（客服专员）

```python
# 职责
处理闲聊、问候、感谢、告别等社交互动，以及无法被其他智能体分类的请求。

# 适用场景
- "你好"
- "谢谢"
- "再见"
- 无法归类的表达

# 核心工具
- get_welcome_message() -> str
- get_quick_help() -> str
- get_system_info() -> str

# 流程
1. 识别消息类型（问候/感谢/告别/其他）
2. 返回对应的标准化回复
3. 必要时引导用户到业务场景
```

## 多智能体扩展指南

如需新增 Agent：

1. 在 `backend/app/ai/agents/` 下新建文件
2. 继承 `BaseAgent`，实现 `run()` 方法
3. 在 `backend/app/ai/agents/__init__.py` 中导出
4. 在 `supervisor.py` 的 `AGENT_MAP` 中注册
5. 在 `classify_intent()` 或 `_keyword_classify()` 中增加对应意图判断

```python
# agents/promotion.py
from app.ai.agents.base import BaseAgent

class PromotionAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="促销专员", description="负责推送优惠活动")

    async def run(self, user_id, message, cart=None):
        return {"response": "今日优惠：全场满100减20！"}
```

## License

MIT
