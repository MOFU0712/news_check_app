from fastapi import APIRouter

router = APIRouter()

@router.post("/markdown")
async def export_markdown():
    """Markdown エクスポート（将来実装）"""
    return {"message": "Export endpoint - Coming soon"}