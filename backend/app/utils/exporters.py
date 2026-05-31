"""
导出工具
"""
from fastapi.responses import PlainTextResponse


def txt_response(content: str, filename: str = "export.txt") -> PlainTextResponse:
    """返回文本文件响应"""
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
