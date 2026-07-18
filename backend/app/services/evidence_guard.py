import re

from ..schemas import CitationRead, EvidenceAudit, EvidenceClaimAudit


_CITATION_PATTERN = re.compile(r"\[(\d+)]")
_SENTENCE_PATTERN = re.compile(r"(?<=[。！？.!?])\s*")
_BULLET_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)、]\s*)")
_MARKDOWN_PATTERN = re.compile(r"[*_`#>|]")
_TEXT_PATTERN = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")


def audit_answer(answer: str, citations: list[CitationRead]) -> EvidenceAudit:
    """Audit whether answer claims point to evidence that can support them.

    EvidenceGuard is deliberately local and deterministic. It checks citation
    integrity and character n-gram coverage instead of asking another LLM to
    judge the first model, so the result is reproducible and works offline.
    """
    if "当前知识库中没有找到足够资料" in answer:
        return EvidenceAudit(
            score=100,
            verdict="no_evidence",
            total_claims=0,
            supported_claims=0,
            weak_claims=0,
            unsupported_claims=0,
            invalid_citation_indices=[],
            claims=[],
        )

    claims = _extract_claims(answer)
    claim_audits: list[EvidenceClaimAudit] = []
    invalid_indices: set[int] = set()

    for claim in claims:
        indices = [int(value) for value in _CITATION_PATTERN.findall(claim)]
        valid_indices = [index for index in indices if 1 <= index <= len(citations)]
        invalid_indices.update(index for index in indices if index not in valid_indices)

        if not indices:
            status = "unsupported"
            support_score = 0.0
            reason = "该结论没有标注引用编号。"
        elif not valid_indices:
            status = "unsupported"
            support_score = 0.0
            reason = "引用编号不存在，无法定位到检索证据。"
        else:
            support_score = max(
                _claim_support_score(claim, citations[index - 1].quote)
                for index in valid_indices
            )
            if support_score >= 0.18:
                status = "supported"
                reason = "引用有效，且结论与所引原文具有较高文本支持度。"
            else:
                status = "weak"
                reason = "引用有效，但结论与所引原文的直接文本支持较弱，建议人工复核。"

        claim_audits.append(EvidenceClaimAudit(
            claim=claim,
            citation_indices=indices,
            status=status,
            support_score=round(support_score, 3),
            reason=reason,
        ))

    total = len(claim_audits)
    supported = sum(item.status == "supported" for item in claim_audits)
    weak = sum(item.status == "weak" for item in claim_audits)
    unsupported = total - supported - weak
    score = round((supported + weak * 0.5) / total * 100) if total else 100
    if unsupported == 0 and weak == 0:
        verdict = "grounded"
    elif score >= 50:
        verdict = "partially_grounded"
    else:
        verdict = "ungrounded"

    return EvidenceAudit(
        score=score,
        verdict=verdict,
        total_claims=total,
        supported_claims=supported,
        weak_claims=weak,
        unsupported_claims=unsupported,
        invalid_citation_indices=sorted(invalid_indices),
        claims=claim_audits,
    )


def _extract_claims(answer: str) -> list[str]:
    claims: list[str] = []
    in_code_block = False
    for raw_line in answer.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or not line or line.startswith("#"):
            continue
        line = _BULLET_PATTERN.sub("", line)
        if not line or re.fullmatch(r"[-:|\s]+", line):
            continue
        for sentence in _SENTENCE_PATTERN.split(line):
            sentence = sentence.strip()
            plain = _normalise(sentence)
            if len(plain) >= 6:
                claims.append(sentence)
    return claims


def _claim_support_score(claim: str, evidence: str) -> float:
    claim_text = _normalise(_CITATION_PATTERN.sub("", claim))
    evidence_text = _normalise(evidence)
    claim_grams = _ngrams(claim_text)
    evidence_grams = _ngrams(evidence_text)
    if not claim_grams or not evidence_grams:
        return 0.0
    return len(claim_grams & evidence_grams) / len(claim_grams)


def _normalise(text: str) -> str:
    text = _MARKDOWN_PATTERN.sub("", text).lower()
    return "".join(_TEXT_PATTERN.findall(text))


def _ngrams(text: str, size: int = 2) -> set[str]:
    if len(text) < size:
        return {text} if text else set()
    return {text[index:index + size] for index in range(len(text) - size + 1)}
