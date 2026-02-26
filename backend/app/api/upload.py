from fastapi import APIRouter, HTTPException, UploadFile

from app.services.document_service import process_pdf

router = APIRouter()

ALLOWED_CONTENT_TYPES = {"application/pdf"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/upload")
async def upload_document(file: UploadFile):
    # 校验文件类型
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    # 校验文件大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小不能超过 50MB")
    # 重置指针供后续读取
    await file.seek(0)

    chunks_count = await process_pdf(file)
    return {"status": "success", "chunks_count": chunks_count}
