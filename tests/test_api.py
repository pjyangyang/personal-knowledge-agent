from io import BytesIO

import fitz
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base, get_db
from app.main import app


def pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def test_health_and_pdf_query(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "uploads")
    settings.storage_dir.mkdir()

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            assert client.get("/health").json()["status"] == "ok"
            kb = client.post("/api/knowledge-bases", json={"name": "论文资料库"})
            assert kb.status_code == 201
            kb_id = kb.json()["id"]
            renamed = client.patch(f"/api/knowledge-bases/{kb_id}", json={"name": "联邦学习资料库"})
            assert renamed.json()["name"] == "联邦学习资料库"
            response = client.post(
                f"/api/knowledge-bases/{kb_id}/documents",
                files={"file": ("paper.pdf", BytesIO(pdf_bytes("Federated learning protects raw data.")), "application/pdf")},
            )
            assert response.status_code == 201
            query = client.post(f"/api/knowledge-bases/{kb_id}/query", json={"question": "raw data"})
            assert query.status_code == 200
            assert query.json()["evidence_found"] is True
            assert query.json()["citations"][0]["page_number"] == 1
    finally:
        app.dependency_overrides.clear()
