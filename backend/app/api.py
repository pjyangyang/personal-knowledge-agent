import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Document, DocumentChunk, KnowledgeBase
from .schemas import (CitationRead, DocumentRead, KnowledgeBaseCreate, KnowledgeBaseRead,
                      KnowledgeBaseUpdate, QueryRequest, QueryResponse)
from .services.pdf_parser import chunk_pages, extract_pdf
from .services.retrieval import search_chunks

router = APIRouter()


@router.post("/knowledge-bases", response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(payload: KnowledgeBaseCreate, db: Session = Depends(get_db)):
    item = KnowledgeBase(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseRead])
def list_knowledge_bases(db: Session = Depends(get_db)):
    return list(db.scalars(select(KnowledgeBase).order_by(KnowledgeBase.id.desc())))


@router.patch("/knowledge-bases/{knowledge_base_id}", response_model=KnowledgeBaseRead)
def update_knowledge_base(knowledge_base_id: int, payload: KnowledgeBaseUpdate, db: Session = Depends(get_db)):
    item = require_kb(db, knowledge_base_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/knowledge-bases/{knowledge_base_id}", status_code=204)
def delete_knowledge_base(knowledge_base_id: int, db: Session = Depends(get_db)):
    item = require_kb(db, knowledge_base_id)
    paths = [Path(document.storage_path) for document in item.documents]
    db.delete(item)
    db.commit()
    for path in paths:
        path.unlink(missing_ok=True)


@router.get("/knowledge-bases/{knowledge_base_id}/documents", response_model=list[DocumentRead])
def list_documents(knowledge_base_id: int, db: Session = Depends(get_db)):
    require_kb(db, knowledge_base_id)
    return list(db.scalars(select(Document).where(Document.knowledge_base_id == knowledge_base_id)))


@router.post("/knowledge-bases/{knowledge_base_id}/documents", response_model=DocumentRead, status_code=201)
def upload_pdf(knowledge_base_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    require_kb(db, knowledge_base_id)
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(415, "当前 MVP 只支持 PDF 文件")
    content = file.file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(413, "文件超过大小限制")
    digest = hashlib.sha256(content).hexdigest()
    existing = db.scalar(select(Document).where(Document.knowledge_base_id == knowledge_base_id, Document.content_sha256 == digest))
    if existing:
        raise HTTPException(409, f"文件已存在，document_id={existing.id}")
    path = settings.storage_dir / f"{digest}.pdf"
    path.write_bytes(content)
    try:
        pages = extract_pdf(path)
        if not pages:
            raise ValueError("PDF 中没有提取到文本；扫描版 PDF 需要后续 OCR 支持")
        document = Document(knowledge_base_id=knowledge_base_id, filename=file.filename,
                            content_sha256=digest, storage_path=str(path), page_count=len(pages), status="INDEXING")
        db.add(document)
        db.flush()
        for index, (page, text) in enumerate(chunk_pages(pages)):
            db.add(DocumentChunk(document_id=document.id, page_number=page, chunk_index=index, text=text))
        document.status = "INDEXED"
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:
        db.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(422, f"PDF 处理失败：{exc}") from exc


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "文档不存在")
    Path(document.storage_path).unlink(missing_ok=True)
    db.delete(document)
    db.commit()


@router.post("/knowledge-bases/{knowledge_base_id}/query", response_model=QueryResponse)
def query_knowledge_base(knowledge_base_id: int, payload: QueryRequest, db: Session = Depends(get_db)):
    require_kb(db, knowledge_base_id)
    matches = search_chunks(db, knowledge_base_id, payload.question, payload.top_k)
    if not matches:
        return QueryResponse(answer="当前知识库中没有找到足够资料，无法可靠回答该问题。", citations=[], evidence_found=False)
    citations = [CitationRead(document_id=chunk.document_id, filename=chunk.document.filename,
                              page_number=chunk.page_number, chunk_id=chunk.id, quote=chunk.text,
                              score=round(score, 4)) for score, chunk in matches]
    context = "\n".join(f"[{i + 1}] {c.filename} 第 {c.page_number} 页：{c.quote}" for i, c in enumerate(citations))
    answer = f"已找到 {len(citations)} 条相关资料。当前版本只完成检索，尚未接入大语言模型。\n\n{context}"
    return QueryResponse(answer=answer, citations=citations, evidence_found=True)


def require_kb(db: Session, knowledge_base_id: int) -> KnowledgeBase:
    item = db.get(KnowledgeBase, knowledge_base_id)
    if not item:
        raise HTTPException(404, "知识库不存在")
    return item
