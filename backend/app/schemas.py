from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None


class KnowledgeBaseRead(KnowledgeBaseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    status: str
    page_count: int
    created_at: datetime
    error_message: str | None = None
    source_url: str | None = None
    source_type: str
    ocr_used: bool


class CitationRead(BaseModel):
    document_id: int
    filename: str
    page_number: int
    chunk_id: int
    quote: str
    score: float
    source_url: str | None = None


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    conversation_id: int | None = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationRead]
    evidence_found: bool
    conversation_id: int
    message_id: int


class WebpageImportRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class SummaryRequest(BaseModel):
    document_id: int | None = None
    instruction: str = Field(default="请总结资料的核心观点、方法、结论和局限性。", max_length=1000)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    knowledge_base_id: int
    title: str
    created_at: datetime


class MessageRead(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    citations: list[CitationRead] = []


class ConversationDetail(ConversationRead):
    messages: list[MessageRead]
