from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import router
from .db import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Personal Knowledge Agent", version="0.1.0", lifespan=lifespan)
app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}
