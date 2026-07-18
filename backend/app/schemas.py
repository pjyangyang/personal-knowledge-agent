from datetime import datetime

from typing import Literal

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
    top_k: int | None = Field(default=None, ge=1, le=20)
    conversation_id: int | None = None
    skill_id: str = "general_qa"


class EvidenceClaimAudit(BaseModel):
    claim: str
    citation_indices: list[int]
    status: Literal["supported", "weak", "unsupported"]
    support_score: float
    reason: str


class EvidenceAudit(BaseModel):
    score: int
    verdict: Literal["grounded", "partially_grounded", "ungrounded", "no_evidence"]
    total_claims: int
    supported_claims: int
    weak_claims: int
    unsupported_claims: int
    invalid_citation_indices: list[int]
    claims: list[EvidenceClaimAudit]


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationRead]
    evidence_found: bool
    conversation_id: int
    message_id: int
    skill_id: str = "general_qa"
    evidence_audit: EvidenceAudit


class SkillRead(BaseModel):
    id: str
    name: str
    description: str
    category: str
    top_k: int


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
    evidence_audit: EvidenceAudit | None = None


class ConversationDetail(ConversationRead):
    messages: list[MessageRead]
