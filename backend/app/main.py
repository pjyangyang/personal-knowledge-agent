from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from .api import router
from .db import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    yield


def ensure_schema() -> None:
    if engine.dialect.name != "sqlite":
        return
    columns = {column["name"] for column in inspect(engine).get_columns("documents")}
    with engine.begin() as connection:
        if "source_url" not in columns:
            connection.execute(text("ALTER TABLE documents ADD COLUMN source_url VARCHAR(2000)"))
        if "source_type" not in columns:
            connection.execute(text("ALTER TABLE documents ADD COLUMN source_type VARCHAR(20) NOT NULL DEFAULT 'file'"))


app = FastAPI(title="Personal Knowledge Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/app", StaticFiles(directory=frontend_dist, html=True), name="frontend")
