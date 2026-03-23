from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    yield


app = FastAPI(title="CineAI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/jobs", StaticFiles(directory=str(settings.jobs_dir)), name="jobs")
app.include_router(router, prefix="/api")
