# 点餐机器人 · 美味餐厅

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue-3.x-green)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Handoff-orange)](https://langchain-ai.github.io/langgraph/)

> 一个基于 **FastAPI + Vue 3 + LangGraph Handoff 多智能体 + 智谱 AI** 的智能点餐与商家管理系统。支持自然语言点餐、拍照搜菜、语音交互、订单管理、商家后台等功能。

---

## 目录

- [项目简介](#项目简介)
- [核心亮点](#核心亮点)
- [技术架构](#技术架构)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [核心功能](#核心功能)
- [API 概览](#api-概览)
- [配置说明](#配置说明)
- [测试](#测试)
- [部署](#部署)
- [扩展开发](#扩展开发)
- [常见问题](#常见问题)

---

## 项目简介

“美味餐厅”点餐机器人让用户像和朋友聊天一样完成点餐：

- 顾客通过聊天界面说“我要一份宫保鸡丁加米饭”即可自动加购、下单；
- 商家通过后台管理菜品、查看订单、导出订单；
- AI 侧采用 **LangGraph Handoff 多智能体架构**，Supervisor 轻量分流 + 4 个专业 Agent 自由转交，既能处理复杂语义，又通过“快速通道”保证高频意图响应迅速。

---

## 核心亮点

- 🤖 **Handoff 多智能体**：Supervisor 识别意图后交给 Order / Inquiry / Recommend / Service Agent，Agent 之间可主动转交。
- ⚡ **高频意图快速通道**：“下单/菜单/推荐/订单/购物车”等常见说法优先走规则路由，无需 LLM，降低延迟与成本。
- 🔍 **轻量 RAG 检索**：向量检索 + BM25 混合，RRF 融合，失败自动降级，不阻塞对话。
- 🧠 **三层记忆**：Buffer 短期记忆 + Summary 摘要记忆 + Vector 语义记忆。
- 📷 **拍照搜菜**：上传菜品图片，调用智谱视觉模型识别并推荐相似菜品。
- 🎙️ **语音交互**：支持语音输入与播报（浏览器 Web Speech API）。
- 📊 **订单分页与导出**：顾客端“我的订单”、商家端“订单管理”均支持分页与导出。

---

## 技术架构

### 多智能体 Handoff 流程

```
用户输入
    │
    ▼
┌─────────────┐
│  Supervisor │  轻量意图分流（快速通道优先命中则跳过 LLM）
└──────┬──────┘
       │
       ├── 点餐意图 ──▶ Order Agent（加购、下单、购物车）
       ├── 咨询意图 ──▶ Inquiry Agent（菜单、菜品详情）
       ├── 推荐意图 ──▶ Recommend Agent（菜品推荐）
       └── 服务意图 ──▶ Service Agent（店铺信息、订单、FAQ）

各 Agent 可通过 Command(goto="another_agent") 主动转交
```

- 所有工具基于 `ToolContext` 实现，直接调用 `services/` 层，操作真实数据库状态。
- 工具白名单 `AGENT_TOOL_MAP` 控制每个 Agent 可见的工具，避免越权。
- 提示词与知识库全部 Markdown 化，集中存放在 `backend/prompts/` 与 `backend/knowledge/`，由 `content_loader.py` 统一加载。

### 快速通道（Fast Router）

针对高频确定性意图，先由 `app/ai/routing/fast_router.py` 做规则匹配：

| 命中示例 | 处理 |
|----------|------|
| “我要下单 / 确认下单 / 结账” | 直接创建订单 |
| “查看菜单 / 有什么菜” | 直接返回菜单 |
| “推荐几个菜” | 基于规则/历史推荐 |
| “我的订单 / 最近订单” | 直接查询订单 |
| “购物车 / 清空购物车” | 查看或清空购物车 |
| “来一份麻婆豆腐，再来两份毛血旺” | 单条消息多道菜加购 |

- 对“点餐 + 咨询/服务”的混合意图，快速通道主动让行，交给 Agent 统一处理，避免只回应一半。
- 对“可以给我来一杯可乐吗？”这类带语气词的纯点餐请求，不会被误判为混合意图。

未命中时，再走 Handoff LLM 通道。

### 轻量 RAG 检索

- **单查询混合检索**：向量检索 + BM25，RRF 融合，Top-K 返回。
- **无 LLM 重写/扩展/重排序**：减少不稳定 LLM 调用，提升响应速度。
- **失败降级**：检索失败时返回空上下文，不阻塞对话。

### 记忆管理

- **短期记忆**：内存滑动窗口，保留最近 N 轮对话。
- **摘要记忆**：超长对话自动摘要，持久化到 Redis/MongoDB。
- **向量记忆**：历史对话向量化，支持语义相似检索。

> 已移除用户画像/实体记忆提取，不再根据忌口、偏好等限制用户点餐。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + TypeScript + Element Plus + Pinia + Vue Router |
| 后端 | FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 |
| AI 框架 | LangGraph + LangChain + Tool Calling |
| 大模型 | 智谱 AI `glm-4.5-air` |
| 视觉模型 | 智谱 AI `glm-4.6v` |
| Embedding | 智谱 `embedding-3`（512 维） |
| 向量库 | Chroma |
| 数据库 | MySQL（结构化）+ MongoDB（半结构化，可选） |
| 缓存 | Redis（菜单缓存、限流、对话历史缓存） |
| 检索 | BM25 + Dense Retrieval + RRF Fusion |

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- MongoDB 4.4+（可选，不启动时自动降级）
- Redis（可选，用于缓存和限流）

### 1. 克隆项目

```bash
git clone <项目地址>
cd 点餐机器人
```

### 2. 安装后端依赖

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

cd backend
pip install -r requirements.txt

# 复制环境变量模板
cp .env.example .env
# 编辑 .env，填入你的 ZHIPU_API_KEY
```

### 3. 安装前端依赖

```bash
cd ../frontend
npm install
```

### 4. 启动服务

```bash
# 回到项目根目录
cd ..

# 开发模式：同时启动前后端
python start.py

# 生产模式：构建前端并作为静态资源由后端 served
python start.py --prod
```

启动后访问：

| 服务 | 地址 |
|------|------|
| 前端（开发模式） | http://localhost:5173 |
| 后端 API | http://127.0.0.1:8001 |
| API 文档（Swagger） | http://127.0.0.1:8001/docs |
| API 文档（ReDoc） | http://127.0.0.1:8001/redoc |

> `start.py` 会自动检查并清理被占用的 `8001` 端口，Windows 下还会将控制台编码设为 UTF-8。

---

## 项目结构

```
点餐机器人/
├── start.py                  # 一键启动脚本（开发 / 生产）
├── README.md
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── main.py           # 应用入口
│   │   ├── core/             # 配置、数据库、MongoDB、Redis、Chroma、日志、内容加载器
│   │   │   └── content_loader.py  # Markdown 知识库 / 提示词统一加载
│   │   ├── models/           # SQLAlchemy ORM 模型
│   │   ├── schemas/          # Pydantic 数据模型
│   │   ├── repositories/     # 数据访问层
│   │   ├── services/         # 业务逻辑层
│   │   ├── api/              # API 路由
│   │   ├── ai/               # AI 核心层
│   │   │   ├── agents/       # Agent 节点（handoff）
│   │   │   ├── graph/        # LangGraph 工作流构建
│   │   │   ├── rag/          # 轻量 RAG 检索
│   │   │   ├── memory/       # 记忆管理
│   │   │   ├── routing/      # 快速通道路由 + LLM 意图分类器
│   │   │   └── tools/        # ToolContext 工具实现与注册
│   │   └── utils/            # 工具函数
│   ├── knowledge/            # Markdown 化知识库（菜单、FAQ、店铺文档）
│   ├── prompts/              # Markdown 化提示词（Supervisor / Agent / Service）
│   ├── data/                 # 模拟数据与初始化脚本
│   ├── tests/                # 测试用例
│   └── requirements.txt
│
└── frontend/                 # Vue 3 前端
    ├── src/
    │   ├── app/              # 应用入口、布局、路由
    │   ├── features/         # 业务功能（聊天、菜单、订单、购物车等）
    │   ├── modules/admin/    # 商家后台
    │   ├── shared/           # 共享 API、类型、常量、工具
    │   └── views/            # 页面视图
    ├── package.json
    └── vite.config.ts
```

---

## 核心功能

### 顾客端

- 智能点餐对话（Handoff 多智能体协作）
- 数字人交互（SVG 动画）
- 语音输入 / 播报
- 拍照搜菜
- 菜单浏览
- 购物车管理
- 我的订单（分页、导出）

### 商家端

- 商品管理（增删改查）
- 订单管理（分页、导出）
- 全部订单导出

### AI 能力

- **Handoff 多智能体**：Supervisor 轻量分流 + 4 个专业 Agent 自由转交
- **轻量 RAG**：单查询混合检索，无 LLM 重写/扩展/重排序
- **长期记忆**：Buffer + Summary + Vector 三层记忆
- **工具调用**：Agent 绑定专属工具，工具直接操作业务状态
- **用户身份注入**：使用用户名让对话更亲切，不再提取忌口/偏好画像

---

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/login` | 登录 |
| GET | `/api/v1/menu` | 获取菜单 |
| POST | `/api/v1/chat` | 聊天 |
| POST | `/api/v1/chat/stream` | 聊天（SSE 流式） |
| POST | `/api/v1/order` | 创建订单 |
| GET | `/api/v1/orders` | 我的订单（分页） |
| GET | `/api/v1/orders/count` | 我的订单总数 |
| POST | `/api/v1/image/search` | 图片搜菜 |
| GET | `/api/v1/admin/menu` | 商家菜品管理 |
| GET | `/api/v1/admin/orders` | 商家订单管理（分页） |
| GET | `/api/v1/admin/orders/count` | 商家订单总数 |

完整接口文档见启动后的 Swagger UI：`http://127.0.0.1:8001/docs`

---

## 配置说明

编辑 `backend/.env`：

```env
# 必填：智谱 AI API Key（推荐设置为系统环境变量，不要在代码仓库中写入明文）
ZHIPU_API_KEY=your-api-key

# 模型配置（可选）
CHAT_MODEL=glm-4.5-air
EMBEDDING_MODEL=embedding-3
EMBEDDING_DIMENSIONS=512
VISION_MODEL=glm-4.6v

# 数据存储（可选，默认连接本地服务）
DATABASE_URL=mysql+aiomysql://root:123456@localhost:3306/shuxiangge_bot
MONGODB_URL=mongodb://localhost:27017/shuxiangge_bot
REDIS_URL=redis://localhost:6379/0

# 调试模式（可选）
DEBUG=false

# RAG 轻量模式：网络不稳定时设为 true，关闭多查询扩展与 LLM 重排序
RAG_LITE=false
```

---

## 测试

### 后端测试

```bash
cd backend

# 单元测试
pytest tests/unit

# 全部测试
pytest tests
```

### 前端检查

```bash
cd frontend

# TypeScript 类型检查
npm run type-check

# 生产构建
npm run build
```

---

## 部署

### 使用 start.py 一键部署

```bash
python start.py --prod
```

生产模式会：

1. 自动安装/检查 Node.js 环境；
2. 执行 `npm run build` 构建前端；
3. 让 FastAPI 在 `8001` 端口同时提供 API 与静态文件服务。

### 手动部署

```bash
cd frontend
npm install
npm run build

cd ../backend
# 设置环境变量后启动
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

> 生产环境建议通过 Nginx / Caddy 反向代理，并配置 HTTPS。

---

## 扩展开发

### 新增智能体

1. 在 `backend/app/ai/agents/nodes.py` 创建新的 Agent 异步函数，返回 `dict` 或 `Command`。
2. 在 `backend/app/ai/graph/builder.py` 添加节点并设置入口/兜底边。
3. 在 `backend/app/ai/agents/prompts.py` 编写系统提示词。
4. 在 `backend/app/ai/tools/registry.py` 的 `AGENT_TOOL_MAP` 中配置该 Agent 可用工具。

### 新增工具

1. 在 `backend/app/ai/tools/` 下对应 Mixin 文件（如 `cart.py`、`order.py`）中添加异步方法。
2. 在 `backend/app/ai/tools/registry.py` 的 `build_tool_definitions` 中注册工具。
3. 将工具名加入 `AGENT_TOOL_MAP` 对应 Agent 的白名单。

### 新增菜品 / FAQ / 店铺文档

1. 编辑 `backend/knowledge/menu/` 下的 Markdown 文件添加菜品。
2. 编辑 `backend/knowledge/faq/` 下的 Markdown 文件添加 FAQ。
3. 编辑 `backend/knowledge/store/` 下的 Markdown 文件添加店铺信息。
4. 重启服务后 `content_loader.py` 会自动重新加载并构建 RAG 索引。

### 修改提示词

编辑 `backend/prompts/` 下对应的 Markdown 文件（如 `supervisor.md`），无需修改代码即可生效。

---

## 常见问题

### Q：启动时提示端口 8001 被占用？

`python start.py` 会自动尝试结束占用 8001 的进程。若失败，可手动结束：

```bash
# Windows
netstat -ano | findstr :8001
taskkill /PID <PID> /F

# macOS / Linux
lsof -ti:8001 | xargs kill -9
```

### Q：智谱 API 调用失败？

请确认：

1. `backend/.env` 中 `ZHIPU_API_KEY` 已正确填写；
2. 密钥有额度且网络可访问智谱 API；
3. 如网络不稳定，可开启 `RAG_LITE=true` 降低复杂度。

### Q：LLM 响应慢？

- 高频意图已走快速通道，无需调用 LLM；
- 复杂查询才会进入 Agent，响应速度取决于模型和 Embedding 接口；
- 可考虑关闭 RAG 扩展或换用更快的模型。

### Q：Windows 控制台日志显示乱码？

`start.py` 已自动设置 `chcp 65001` 与 Python UTF-8 编码。若仍有乱码，请确保终端字体支持中文（如 Microsoft YaHei、Consolas）。


