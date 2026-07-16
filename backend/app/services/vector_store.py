from dataclasses import dataclass
from threading import Lock

from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models

from ..config import settings
from ..models import DocumentChunk


@dataclass
class VectorMatch:
    chunk_id: int
    score: float


class VectorStore:
    def __init__(self) -> None:
        self._client: QdrantClient | None = None
        self._model: TextEmbedding | None = None
        self._lock = Lock()

    def _ensure_ready(self) -> tuple[QdrantClient, TextEmbedding]:
        if self._client is not None and self._model is not None:
            return self._client, self._model
        with self._lock:
            if self._client is None:
                self._client = QdrantClient(path=str(settings.qdrant_path))
                if not self._client.collection_exists(settings.vector_collection):
                    self._client.create_collection(
                        collection_name=settings.vector_collection,
                        vectors_config=models.VectorParams(
                            size=settings.embedding_dimension,
                            distance=models.Distance.COSINE,
                        ),
                    )
            if self._model is None:
                self._model = TextEmbedding(
                    model_name=settings.embedding_model,
                    cache_dir=str(settings.model_cache_dir),
                )
        return self._client, self._model

    def index_chunks(self, knowledge_base_id: int, document_id: int, chunks: list[DocumentChunk]) -> None:
        if not chunks:
            return
        client, model = self._ensure_ready()
        vectors = list(model.passage_embed([chunk.text for chunk in chunks]))
        points = [
            models.PointStruct(
                id=chunk.id,
                vector=vector.tolist(),
                payload={
                    "chunk_id": chunk.id,
                    "document_id": document_id,
                    "knowledge_base_id": knowledge_base_id,
                    "page_number": chunk.page_number,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        client.upsert(collection_name=settings.vector_collection, points=points, wait=True)

    def search(self, knowledge_base_id: int, question: str, limit: int) -> list[VectorMatch]:
        client, model = self._ensure_ready()
        query_vector = next(iter(model.query_embed(question))).tolist()
        response = client.query_points(
            collection_name=settings.vector_collection,
            query=query_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="knowledge_base_id",
                        match=models.MatchValue(value=knowledge_base_id),
                    )
                ]
            ),
            limit=limit,
            with_payload=True,
        )
        return [
            VectorMatch(chunk_id=int(point.payload["chunk_id"]), score=float(point.score))
            for point in response.points
            if point.payload and "chunk_id" in point.payload
        ]

    def delete_document(self, document_id: int) -> None:
        client, _ = self._ensure_ready()
        client.delete(
            collection_name=settings.vector_collection,
            points_selector=models.Filter(
                must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))]
            ),
            wait=True,
        )

    def delete_knowledge_base(self, knowledge_base_id: int) -> None:
        client, _ = self._ensure_ready()
        client.delete(
            collection_name=settings.vector_collection,
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(
                        key="knowledge_base_id",
                        match=models.MatchValue(value=knowledge_base_id),
                    )
                ]
            ),
            wait=True,
        )


vector_store = VectorStore()
