"""Lightweight static media server for generated voicelines."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from runtime_layout import LAYOUT

VOICELINES_DIR = LAYOUT.voicelines_dir

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/__health")
async def health():
    return {"status": "ok"}


app.mount("/voicelines", StaticFiles(directory=VOICELINES_DIR), name="voicelines")
