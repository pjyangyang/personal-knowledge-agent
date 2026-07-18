from app.schemas import CitationRead
from app.services.evidence_guard import audit_answer


def citation(quote: str) -> CitationRead:
    return CitationRead(
        document_id=1,
        filename="paper.pdf",
        page_number=3,
        chunk_id=10,
        quote=quote,
        score=0.9,
    )


def test_evidence_guard_marks_supported_and_unsupported_claims():
    audit = audit_answer(
        "联邦学习可以避免直接汇集原始数据[1]。但是它能完全消除隐私风险。",
        [citation("联邦学习让参与方在不直接传输原始数据的情况下协同训练。")],
    )

    assert audit.total_claims == 2
    assert audit.supported_claims == 1
    assert audit.unsupported_claims == 1
    assert audit.score == 50
    assert audit.verdict == "partially_grounded"


def test_evidence_guard_rejects_missing_citation_index():
    audit = audit_answer("实验准确率达到百分之九十[3]。", [citation("实验准确率为 90%。")])

    assert audit.invalid_citation_indices == [3]
    assert audit.claims[0].status == "unsupported"
    assert audit.verdict == "ungrounded"


def test_evidence_guard_accepts_insufficient_evidence_response():
    audit = audit_answer("当前知识库中没有找到足够资料，无法可靠回答该问题。", [])

    assert audit.verdict == "no_evidence"
    assert audit.total_claims == 0
