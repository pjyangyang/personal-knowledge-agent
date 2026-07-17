import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .db import get_db
from .models import Citation, Conversation, Document, DocumentChunk, KnowledgeBase, Message
from .schemas import (CitationRead, DocumentRead, KnowledgeBaseCreate, KnowledgeBaseRead,
                      KnowledgeBaseUpdate, ConversationDetail, ConversationRead, MessageRead,
                      QueryRequest, QueryResponse, SummaryRequest, WebpageImportRequest)
from .services.generation import generate_answer, stream_answer
from .services.document_parser import SUPPORTED_EXTENSIONS, extract_document
from .services.pdf_parser import PageText, chunk_pages
from .services.retrieval import search_chunks
from .services.vector_store import vector_store
from .services.web_import import fetch_webpage

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
    vector_store.delete_knowledge_base(knowledge_base_id)
    db.delete(item)
    db.commit()
    for path in paths:
        path.unlink(missing_ok=True)


@router.get("/knowledge-bases/{knowledge_base_id}/documents", response_model=list[DocumentRead])
def list_documents(knowledge_base_id: int, db: Session = Depends(get_db)):
    require_kb(db, knowledge_base_id)
    return list(db.scalars(select(Document).where(Document.knowledge_base_id == knowledge_base_id)))


@router.post("/knowledge-bases/{knowledge_base_id}/documents", response_model=DocumentRead, status_code=201)
def upload_document(knowledge_base_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    require_kb(db, knowledge_base_id)
    extension = Path(file.filename or "").suffix.lower()
    if not file.filename or extension not in SUPPORTED_EXTENSIONS:
        supported = "、".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(415, f"当前支持的文件格式：{supported}")
    content = file.file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(413, "文件超过大小限制")
    digest = hashlib.sha256(content).hexdigest()
    existing = db.scalar(select(Document).where(Document.knowledge_base_id == knowledge_base_id, Document.content_sha256 == digest))
    if existing:
        raise HTTPException(409, f"文件已存在，document_id={existing.id}")
    path = settings.storage_dir / f"{digest}{extension}"
    path.write_bytes(content)
    try:
        pages, ocr_used = extract_document(path, extension)
        if not pages:
            if extension == ".pdf":
                raise ValueError("PDF 中没有提取到文本；扫描版 PDF 需要 OCR 支持")
            raise ValueError("文档中没有提取到可索引文本")
        document = Document(knowledge_base_id=knowledge_base_id, filename=file.filename,
                            content_sha256=digest, storage_path=str(path), page_count=len(pages),
                            status="INDEXING", source_type=extension.removeprefix("."), ocr_used=ocr_used)
        db.add(document)
        db.flush()
        for index, (page, text) in enumerate(chunk_pages(pages)):
            db.add(DocumentChunk(document_id=document.id, page_number=page, chunk_index=index, text=text))
        db.flush()
        vector_store.index_chunks(knowledge_base_id, document.id, list(document.chunks))
        document.status = "INDEXED"
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:
        db.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(422, f"文档处理失败：{exc}") from exc


@router.post("/knowledge-bases/{knowledge_base_id}/webpages", response_model=DocumentRead, status_code=201)
def import_webpage(knowledge_base_id: int, payload: WebpageImportRequest, db: Session = Depends(get_db)):
    require_kb(db, knowledge_base_id)
    digest = hashlib.sha256(payload.url.encode("utf-8")).hexdigest()
    existing = db.scalar(select(Document).where(Document.knowledge_base_id == knowledge_base_id,
                                                Document.content_sha256 == digest))
    if existing:
        raise HTTPException(409, f"网页已存在，document_id={existing.id}")
    path = settings.storage_dir / f"{digest}.txt"
    try:
        title, text_content = fetch_webpage(payload.url, path)
        document = Document(knowledge_base_id=knowledge_base_id, filename=title,
                            content_sha256=digest, storage_path=str(path), page_count=1,
                            status="INDEXING", source_url=payload.url, source_type="webpage")
        db.add(document)
        db.flush()
        for index, (page, text) in enumerate(chunk_pages([PageText(page_number=1, text=text_content)])):
            db.add(DocumentChunk(document_id=document.id, page_number=page, chunk_index=index, text=text))
        db.flush()
        vector_store.index_chunks(knowledge_base_id, document.id, list(document.chunks))
        document.status = "INDEXED"
        db.commit()
        db.refresh(document)
        return document
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(422, f"网页处理失败：{exc}") from exc


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "文档不存在")
    Path(document.storage_path).unlink(missing_ok=True)
    vector_store.delete_document(document_id)
    db.delete(document)
    db.commit()


@router.post("/knowledge-bases/{knowledge_base_id}/query", response_model=QueryResponse)
def query_knowledge_base(knowledge_base_id: int, payload: QueryRequest, db: Session = Depends(get_db)):
    require_kb(db, knowledge_base_id)
    conversation = get_or_create_conversation(db, knowledge_base_id, payload)
    user_message = Message(conversation_id=conversation.id, role="user", content=payload.question)
    db.add(user_message)
    db.flush()
    matches = search_chunks(db, knowledge_base_id, payload.question, payload.top_k)
    if not matches:
        citations = []
        answer = generate_answer(payload.question, citations)
        evidence_found = False
    else:
        citations = [CitationRead(document_id=chunk.document_id, filename=chunk.document.filename,
                                  page_number=chunk.page_number, chunk_id=chunk.id, quote=chunk.text,
                                  score=round(score, 4), source_url=chunk.document.source_url) for score, chunk in matches]
        answer = generate_answer(payload.question, citations)
        evidence_found = True
    assistant_message = Message(conversation_id=conversation.id, role="assistant", content=answer)
    db.add(assistant_message)
    db.flush()
    for citation in citations:
        db.add(Citation(message_id=assistant_message.id, chunk_id=citation.chunk_id,
                        document_name=citation.filename, page_number=citation.page_number,
                        quote=citation.quote, score=citation.score))
    db.commit()
    return QueryResponse(answer=answer, citations=citations, evidence_found=evidence_found,
                         conversation_id=conversation.id, message_id=assistant_message.id)


@router.post("/knowledge-bases/{knowledge_base_id}/query/stream")
def stream_query_knowledge_base(knowledge_base_id: int, payload: QueryRequest, db: Session = Depends(get_db)):
    require_kb(db, knowledge_base_id)
    conversation = get_or_create_conversation(db, knowledge_base_id, payload)
    db.add(Message(conversation_id=conversation.id, role="user", content=payload.question))
    matches = search_chunks(db, knowledge_base_id, payload.question, payload.top_k)
    citations = [CitationRead(document_id=chunk.document_id, filename=chunk.document.filename,
                              page_number=chunk.page_number, chunk_id=chunk.id, quote=chunk.text,
                              score=round(score, 4), source_url=chunk.document.source_url)
                 for score, chunk in matches]
    db.commit()
    conversation_id = conversation.id
    stream_session_factory = sessionmaker(bind=db.get_bind(), autoflush=False, autocommit=False)

    def generate_events():
        yield json.dumps({"type": "meta", "conversation_id": conversation_id,
                          "citations": [item.model_dump(mode="json") for item in citations]},
                         ensure_ascii=False) + "\n"
        answer_parts: list[str] = []
        try:
            for token in stream_answer(payload.question, citations):
                answer_parts.append(token)
                yield json.dumps({"type": "token", "content": token}, ensure_ascii=False) + "\n"
            answer = "".join(answer_parts)
            with stream_session_factory() as stream_db:
                assistant = Message(conversation_id=conversation_id, role="assistant", content=answer)
                stream_db.add(assistant)
                stream_db.flush()
                for citation in citations:
                    stream_db.add(Citation(message_id=assistant.id, chunk_id=citation.chunk_id,
                                           document_name=citation.filename, page_number=citation.page_number,
                                           quote=citation.quote, score=citation.score))
                stream_db.commit()
                message_id = assistant.id
            yield json.dumps({"type": "done", "message_id": message_id}, ensure_ascii=False) + "\n"
        except Exception as exc:
            yield json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n"

    return StreamingResponse(generate_events(), media_type="application/x-ndjson",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@router.get("/knowledge-bases/{knowledge_base_id}/conversations", response_model=list[ConversationRead])
def list_conversations(knowledge_base_id: int, db: Session = Depends(get_db)):
    require_kb(db, knowledge_base_id)
    return list(db.scalars(select(Conversation).where(Conversation.knowledge_base_id == knowledge_base_id).order_by(Conversation.id.desc())))


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(404, "对话不存在")
    messages = []
    for message in conversation.messages:
        citations = [CitationRead(document_id=c.chunk.document_id if c.chunk else 0,
                                  filename=c.document_name, page_number=c.page_number,
                                  chunk_id=c.chunk_id or 0, quote=c.quote, score=c.score,
                                  source_url=c.chunk.document.source_url if c.chunk else None)
                     for c in message.citations]
        messages.append(MessageRead(id=message.id, role=message.role, content=message.content,
                                    created_at=message.created_at, citations=citations))
    return ConversationDetail(id=conversation.id, knowledge_base_id=conversation.knowledge_base_id,
                              title=conversation.title, created_at=conversation.created_at, messages=messages)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(404, "对话不存在")
    db.delete(conversation)
    db.commit()


@router.post("/knowledge-bases/{knowledge_base_id}/reindex", response_model=list[DocumentRead])
def reindex_knowledge_base(knowledge_base_id: int, db: Session = Depends(get_db)):
    require_kb(db, knowledge_base_id)
    documents = list(db.scalars(select(Document).where(Document.knowledge_base_id == knowledge_base_id)))
    for document in documents:
        vector_store.index_chunks(knowledge_base_id, document.id, list(document.chunks))
    return documents


@router.post("/knowledge-bases/{knowledge_base_id}/summarize", response_model=QueryResponse)
def summarize_knowledge_base(knowledge_base_id: int, payload: SummaryRequest, db: Session = Depends(get_db)):
    require_kb(db, knowledge_base_id)
    if payload.document_id is not None:
        document = db.get(Document, payload.document_id)
        if not document or document.knowledge_base_id != knowledge_base_id:
            raise HTTPException(404, "文档不存在或不属于当前知识库")
        chunks = list(db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document.id)
                                .order_by(DocumentChunk.chunk_index).limit(40)))
        title = document.filename
    else:
        chunks = list(db.scalars(select(DocumentChunk).join(DocumentChunk.document)
                                .where(Document.knowledge_base_id == knowledge_base_id)
                                .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).limit(40)))
        title = "知识库综合总结"
    citations = [CitationRead(document_id=chunk.document_id, filename=chunk.document.filename,
                              page_number=chunk.page_number, chunk_id=chunk.id, quote=chunk.text,
                              score=1.0, source_url=chunk.document.source_url) for chunk in chunks]
    conversation = Conversation(knowledge_base_id=knowledge_base_id, title=f"总结：{title[:60]}")
    db.add(conversation)
    db.flush()
    answer = generate_answer(payload.instruction, citations)
    user_message = Message(conversation_id=conversation.id, role="user", content=payload.instruction)
    assistant_message = Message(conversation_id=conversation.id, role="assistant", content=answer)
    db.add_all([user_message, assistant_message])
    db.flush()
    for citation in citations:
        db.add(Citation(message_id=assistant_message.id, chunk_id=citation.chunk_id,
                        document_name=citation.filename, page_number=citation.page_number,
                        quote=citation.quote, score=citation.score))
    db.commit()
    return QueryResponse(answer=answer, citations=citations, evidence_found=bool(citations),
                         conversation_id=conversation.id, message_id=assistant_message.id)


def get_or_create_conversation(db: Session, knowledge_base_id: int, payload: QueryRequest) -> Conversation:
    if payload.conversation_id is not None:
        conversation = db.get(Conversation, payload.conversation_id)
        if not conversation or conversation.knowledge_base_id != knowledge_base_id:
            raise HTTPException(404, "对话不存在或不属于当前知识库")
        return conversation
    conversation = Conversation(knowledge_base_id=knowledge_base_id, title=payload.question[:80])
    db.add(conversation)
    db.flush()
    return conversation


def require_kb(db: Session, knowledge_base_id: int) -> KnowledgeBase:
    item = db.get(KnowledgeBase, knowledge_base_id)
    if not item:
        raise HTTPException(404, "知识库不存在")
    return item
