"""
内容与提示词加载器
负责从 Markdown 文件加载知识库数据、提示词模板，并提供统一的变量替换接口。
"""
import os
import re
from io import StringIO
from csv import reader
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from langchain_core.documents import Document

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# backend 目录
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_KNOWLEDGE_DIR = _BACKEND_DIR / "knowledge"
_PROMPTS_DIR = _BACKEND_DIR / "prompts"


class MarkdownContent:
    """Markdown 文件解析结果"""

    def __init__(self, path: Path, frontmatter: Dict[str, Any], body: str):
        self.path = path
        self.frontmatter = frontmatter or {}
        self.body = body.strip()

    @property
    def title(self) -> str:
        return self.frontmatter.get("title", self.path.stem)

    @property
    def source(self) -> str:
        return self.frontmatter.get("source", self.path.parent.name)


def load_markdown(path: str | Path) -> MarkdownContent:
    """
    解析 Markdown 文件，分离 Frontmatter（YAML）与正文。
    支持绝对路径或相对于 backend 根目录的相对路径。
    """
    if isinstance(path, str):
        file_path = Path(path) if os.path.isabs(path) else _BACKEND_DIR / path
    else:
        file_path = path

    if not file_path.exists():
        raise FileNotFoundError(f"Markdown 文件不存在: {file_path}")

    text = file_path.read_text(encoding="utf-8")
    frontmatter: Dict[str, Any] = {}
    body = text

    # 解析 ---\n...\n--- 形式的 YAML Frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError as e:
                logger.warning(f"[ContentLoader] Frontmatter 解析失败 {file_path}: {e}")
            body = parts[2]

    return MarkdownContent(file_path, frontmatter, body)


def render_template(template: str, variables: Dict[str, Any]) -> str:
    """
    简单的 {{variable}} 模板替换。
    未定义的变量保留原样，避免静默错误。
    """
    if not template:
        return ""

    pattern = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

    def replacer(match: re.Match) -> str:
        key = match.group(1)
        if key in variables:
            value = variables[key]
            return str(value) if value is not None else ""
        return match.group(0)

    return pattern.sub(replacer, template)


def load_prompt(name: str, variables: Optional[Dict[str, Any]] = None) -> str:
    """
    加载 prompts 目录下的 Markdown 提示词模板。

    Args:
        name: 相对 prompts 目录的路径，如 "supervisor", "agents/order", "services/greeting"
        variables: 模板变量字典
    """
    prompt_path = _PROMPTS_DIR / f"{name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"提示词文件不存在: {prompt_path}")

    content = load_markdown(prompt_path)
    variables = variables or {}

    # 自动注入共享 identity 规则
    if "identity_rules" not in variables:
        identity_path = _PROMPTS_DIR / "shared" / "identity.md"
        if identity_path.exists():
            identity_body = load_markdown(identity_path).body
            # 去掉最外层标题，避免重复
            identity_body = re.sub(r"^#\s+.*\n+", "", identity_body, count=1)
            variables["identity_rules"] = identity_body.strip()

    return render_template(content.body, variables)


# ---------------------------------------------------------------------------
# 知识库数据加载
# ---------------------------------------------------------------------------

def _parse_markdown_tables(body: str) -> List[Dict[str, str]]:
    """从 Markdown 正文中提取所有表格，合并为行列表"""
    lines = body.splitlines()
    all_rows: List[Dict[str, str]] = []
    current_table: List[str] = []

    def flush_table():
        nonlocal all_rows, current_table
        if len(current_table) < 2:
            current_table = []
            return

        # 解析表头
        header_line = current_table[0]
        headers = [h.strip() for h in header_line.strip("|").split("|")]

        for line in current_table[1:]:
            # 跳过分隔行
            if all(c in "|-: " for c in line):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < len(headers):
                cells.extend([""] * (len(headers) - len(cells)))
            row = {headers[i]: cells[i] for i in range(len(headers))}
            all_rows.append(row)

        current_table = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            current_table.append(stripped)
        else:
            flush_table()

    flush_table()
    return all_rows


def _price_to_float(value: str) -> float:
    """把价格字符串转为 float"""
    cleaned = re.sub(r"[^\d.]", "", value.strip())
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def _int_or_default(value: str, default: int = 0) -> int:
    """把字符串转为 int，失败返回默认值"""
    cleaned = re.sub(r"[^\d-]", "", value.strip())
    try:
        return int(cleaned) if cleaned else default
    except ValueError:
        return default


def get_menu_items() -> List[Dict[str, Any]]:
    """从 knowledge/menu/menu.md 解析完整菜单菜品列表"""
    content = load_markdown(_KNOWLEDGE_DIR / "menu" / "menu.md")
    body = content.body
    lines = body.splitlines()

    items: List[Dict[str, Any]] = []
    current_category = ""
    current_table: List[str] = []

    def flush_table():
        nonlocal items, current_table
        if len(current_table) < 2:
            current_table = []
            return

        header_line = current_table[0]
        headers = [h.strip() for h in header_line.strip("|").split("|")]

        for line in current_table[1:]:
            if all(c in "|-: " for c in line):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < len(headers):
                cells.extend([""] * (len(headers) - len(cells)))
            row = {headers[i]: cells[i] for i in range(len(headers))}

            name = row.get("菜品名称", "").strip()
            if not name:
                continue

            # 如果表格自带分类列则优先使用，否则使用当前章节分类
            category = row.get("分类", "").strip() or current_category

            items.append({
                "name": name,
                "price": _price_to_float(row.get("价格（元）", "")),
                "spicy_level": _int_or_default(row.get("辣度", "")),
                "category": category,
                "tags": row.get("标签", "").strip(),
                "stock": _int_or_default(row.get("库存", "")),
                "description": row.get("描述", "").strip(),
            })

        current_table = []

    for line in lines:
        stripped = line.strip()
        # 更新当前分类（二级标题）
        if stripped.startswith("## ") and not stripped.startswith("## |"):
            flush_table()
            current_category = stripped.replace("## ", "").strip()
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            current_table.append(stripped)
        else:
            flush_table()

    flush_table()
    return items


def get_menu_categories() -> List[Dict[str, Any]]:
    """从 knowledge/menu/categories.md 解析分类列表"""
    content = load_markdown(_KNOWLEDGE_DIR / "menu" / "categories.md")
    rows = _parse_markdown_tables(content.body)

    categories: List[Dict[str, Any]] = []
    for row in rows:
        name = row.get("分类", "").strip()
        if not name:
            continue
        categories.append({
            "name": name,
            "sort_order": _int_or_default(row.get("排序", "")),
            "description": row.get("说明", "").strip(),
        })

    return categories


def get_faq_data() -> List[Dict[str, str]]:
    """从 knowledge/faq/faq.md 解析 FAQ 问答对"""
    content = load_markdown(_KNOWLEDGE_DIR / "faq" / "faq.md")
    body = content.body

    # 按 ## 标题分块
    pattern = re.compile(r"^##\s+(.*?)\n(.*?)(?=^##\s+|\Z)", re.MULTILINE | re.DOTALL)
    matches = pattern.findall(body)

    faq_list: List[Dict[str, str]] = []
    for question, answer in matches:
        q = question.strip()
        a = answer.strip()
        if q and a:
            faq_list.append({"question": q, "answer": a})

    return faq_list


def get_store_docs() -> List[Dict[str, str]]:
    """从 knowledge/store/*.md 解析店铺文档"""
    store_dir = _KNOWLEDGE_DIR / "store"
    docs: List[Dict[str, str]] = []

    if not store_dir.exists():
        return docs

    for file_path in sorted(store_dir.glob("*.md")):
        try:
            content = load_markdown(file_path)
            title = content.frontmatter.get("title", content.title)
            docs.append({
                "title": title,
                "content": content.body.strip(),
                "source": content.source,
                "file": file_path.name,
            })
        except Exception as e:
            logger.warning(f"[ContentLoader] 加载店铺文档失败 {file_path}: {e}")

    return docs


# ---------------------------------------------------------------------------
# RAG Document 构建
# ---------------------------------------------------------------------------

def build_menu_documents() -> List[Document]:
    """构建菜单 RAG 文档"""
    documents: List[Document] = []
    for item in get_menu_items():
        content = (
            f"菜品名称：{item['name']}\n"
            f"描述：{item['description']}\n"
            f"价格：{item['price']:.0f}元\n"
            f"辣度：{item['spicy_level']}级（0-5）\n"
            f"分类：{item['category']}\n"
            f"标签：{item['tags']}\n"
            f"库存：{item['stock']}份"
        )
        documents.append(Document(
            page_content=content,
            metadata={
                "source": "menu",
                "name": item["name"],
                "category": item["category"],
                "spicy_level": item["spicy_level"],
                "price": item["price"],
            }
        ))
    return documents


def build_faq_documents() -> List[Document]:
    """构建 FAQ RAG 文档"""
    documents: List[Document] = []
    for faq in get_faq_data():
        content = f"问题：{faq['question']}\n回答：{faq['answer']}"
        documents.append(Document(
            page_content=content,
            metadata={"source": "faq", "question": faq["question"]}
        ))
    return documents


def build_store_documents() -> List[Document]:
    """构建店铺文档 RAG 文档"""
    documents: List[Document] = []
    for doc in get_store_docs():
        content = f"{doc['title']}\n\n{doc['content']}"
        documents.append(Document(
            page_content=content,
            metadata={
                "source": "store",
                "title": doc["title"],
                "file": doc.get("file", ""),
            }
        ))
    return documents


def load_knowledge_documents() -> Dict[str, List[Document]]:
    """加载所有知识库文档，按 source 分组"""
    return {
        "menu": build_menu_documents(),
        "faq": build_faq_documents(),
        "store": build_store_documents(),
    }


# ---------------------------------------------------------------------------
# 启动校验
# ---------------------------------------------------------------------------

def verify_knowledge_migration() -> Dict[str, Any]:
    """
    校验 Markdown 知识库是否完整。
    返回统计信息，若关键数据缺失则记录警告。
    """
    stats = {
        "menu_items": len(get_menu_items()),
        "categories": len(get_menu_categories()),
        "faq": len(get_faq_data()),
        "store_docs": len(get_store_docs()),
    }

    expected = {
        "menu_items": 39,
        "categories": 7,
        "faq": 20,
        "store_docs": 6,
    }

    for key, count in stats.items():
        exp = expected.get(key)
        if exp and count != exp:
            logger.warning(
                f"[ContentLoader] 知识库校验异常: {key} 期望 {exp} 条，实际 {count} 条"
            )

    if all(stats.get(k) for k in expected):
        logger.info(f"[ContentLoader] 知识库加载成功: {stats}")
    else:
        logger.error(f"[ContentLoader] 知识库加载异常: {stats}")

    return stats
