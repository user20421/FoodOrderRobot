# 智能点餐机器人

> 基于 FastAPI + Vue 3 + LangGraph 多智能体架构 + DashScope 的智能点餐系统

## 项目架构

### 多智能体架构（Supervisor模式）

```
用户输入 → Supervisor Agent（意图识别+路由）
    ├── 点餐意图 → Order Agent（点餐、加购、下单）
    ├── 咨询意图 → Inquiry Agent（菜单查询、菜品详情）
    ├── 推荐意图 → Recommend Agent（个性化推荐）
    └── 服务意图 → Service Agent（店铺信息、订单追踪、FAQ）
```

### 高级RAG引擎

- **多查询扩展**：LLM生成多角度同义查询
- **混合检索**：Dense向量 + Sparse(BM25) + Metadata过滤
- **RRF融合**：Reciprocal Rank Fusion多路召回融合
- **LLM重排序**：智能重排返回最相关结果
- **上下文压缩**：提取关键片段，控制Token消耗

### 高级记忆管理

- **短期记忆**：内存滑动窗口，最近6轮对话
- **摘要记忆**：超长对话自动LLM摘要，MongoDB持久化
- **实体记忆**：提取用户偏好、忌口、常点菜品，构建用户画像
- **向量记忆**：历史对话向量化，支持语义相似检索

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + Element Plus + Pinia + Vue Router |
| 后端 | FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 |
| AI框架 | LangGraph + LangChain + Tool Calling |
| 大模型 | 阿里云 DashScope (qwen-max) |
| 向量库 | Chroma + DashScope Embeddings |
| 数据库 | MySQL (结构化) + MongoDB (半结构化) + Chroma (向量) |
| 检索 | BM25 + Dense Retrieval + RRF Fusion |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- MongoDB 4.4+（可选，用于高级记忆管理）

### 1. 克隆项目

```bash
git clone <项目地址>
cd 点餐机器人
```

### 2. 配置环境

```bash
# 创建Python虚拟环境
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# 安装后端依赖
cd backend
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 DASHSCOPE_API_KEY
```

### 3. 启动服务

```bash
# 回到项目根目录
cd ..

# 一键启动（开发模式）
python start.py

# 生产模式
python start.py --prod
```

启动后访问：
- 前端：`http://localhost:5173`
- 后端API：`http://127.0.0.1:8000`
- API文档：`http://127.0.0.1:8000/docs`

## 项目结构

```
点餐机器人/
├── start.py                  # 一键启动脚本
├── README.md
├── backend/                  # FastAPI后端
│   ├── app/
│   │   ├── main.py           # 应用入口
│   │   ├── core/             # 核心配置（数据库、MongoDB、Chroma）
│   │   ├── models/           # SQLAlchemy ORM模型
│   │   ├── schemas/          # Pydantic数据模型
│   │   ├── repositories/     # 数据访问层
│   │   ├── services/         # 业务逻辑层
│   │   ├── api/              # API路由
│   │   ├── ai/               # AI核心层
│   │   │   ├── agents/       # 多智能体定义
│   │   │   ├── tools/        # 工具定义
│   │   │   ├── graph/        # LangGraph工作流
│   │   │   ├── rag/          # 高级RAG引擎
│   │   │   ├── memory/       # 高级记忆管理
│   │   │   └── prompts/      # 提示词模板
│   │   └── utils/            # 工具函数
│   ├── data/                 # 模拟数据（菜单、FAQ、店铺文档）
│   └── requirements.txt
│
└── frontend/                 # Vue 3前端
    ├── src/
    │   ├── views/            # 页面视图
    │   ├── components/       # 组件
    │   ├── stores/           # Pinia状态管理
    │   ├── api/              # API封装
    │   └── router/           # 路由配置
    └── package.json
```

## 核心功能

### 顾客端
- 智能点餐对话（多智能体协作）
- 数字人交互（SVG动画）
- 语音输入/播报
- 拍照搜菜
- 菜单浏览
- 购物车管理
- 订单查询与导出

### 商家端
- 商品管理（增删改查）
- 订单管理
- 订单导出

### AI能力
- **多智能体协作**：Supervisor路由 + 4个专业Agent
- **高级RAG**：多查询扩展 + 混合检索 + RRF + 重排序 + 压缩
- **长期记忆**：Buffer + Summary + Entity + Vector 四层记忆
- **用户画像**：自动提取偏好、忌口、常点菜品
- **工具调用**：每个Agent绑定专属工具集

## 数据存储

| 存储 | 用途 | 数据 |
|------|------|------|
| MySQL | 结构化数据 | 用户、菜品、订单 |
| MongoDB | 半结构化数据 | 聊天记录、用户画像、对话摘要 |
| Chroma | 向量数据 | 菜单文档、FAQ、店铺文档、对话向量 |

## API接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/auth/register | 注册 |
| POST | /api/v1/auth/login | 登录 |
| GET | /api/v1/menu | 获取菜单 |
| POST | /api/v1/chat | 聊天 |
| POST | /api/v1/order | 创建订单 |
| GET | /api/v1/orders | 订单列表 |
| POST | /api/v1/image/search | 图片搜菜 |
| GET | /api/v1/admin/menu | 商家菜品管理 |
| GET | /api/v1/admin/orders | 商家订单管理 |

## 配置说明

编辑 `backend/.env`：

```env
# 必填
DASHSCOPE_API_KEY=your-api-key

# 可选
CHAT_MODEL=qwen-max          # 对话模型
EMBEDDING_MODEL=text-embedding-v4  # 嵌入模型
DATABASE_URL=mysql+aiomysql://root:123456@localhost:3306/shuxiangge_bot
MONGODB_URL=mongodb://localhost:27017/shuxiangge_bot
```

## 测试账号

- 商家账号：`admin` / `123456`
- 顾客账号：自行注册

## 扩展指南

### 新增智能体
1. 在 `app/ai/agents/` 创建新Agent类，继承 `BaseToolAgent`
2. 在 `app/ai/agents/__init__.py` 注册
3. 在 `app/ai/agents/supervisor.py` 添加意图分类逻辑
4. 在 `app/ai/graph/builder.py` 更新路由

### 新增工具
1. 在 `app/ai/tools/` 创建工具函数，使用 `@tool` 装饰器
2. 在 `app/ai/tools/__init__.py` 导出
3. 在对应Agent中绑定工具

### 新增菜品
编辑 `backend/data/menu_data.py`，添加菜品数据后重启服务即可自动初始化。


