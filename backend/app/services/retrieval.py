from sqlalchemy import select
from sqlalchemy.orm import Session
from sklearn.feature_extraction.text import TfidfVectorizer

from ..models import DocumentChunk


def search_chunks(db: Session, knowledge_base_id: int, question: str, top_k: int = 5):
    chunks = list(
        db.scalars(
            select(DocumentChunk)
            .join(DocumentChunk.document)
            .where(DocumentChunk.document.has(knowledge_base_id=knowledge_base_id))
        )
    )
    if not chunks:
        return []
    texts = [chunk.text for chunk in chunks]
    # Character n-grams work for both Chinese text (without whitespace) and Latin text.
    matrix = TfidfVectorizer(analyzer="char", ngram_range=(2, 4)).fit_transform(texts + [question])
    scores = (matrix[:-1] @ matrix[-1].T).toarray().ravel()
    ranked = sorted(zip(scores, chunks), key=lambda item: item[0], reverse=True)
    return [(float(score), chunk) for score, chunk in ranked[:top_k] if score > 0]
