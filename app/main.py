"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        init_db()
    except Exception as e:
        print(f"Warning: could not init DB on startup: {e}")
    yield
    # Shutdown


app = FastAPI(
    title="TemplateLab Metadata API",
    description=(
        "Read-only API over publicly extracted TemplateLab template metadata. "
        "Does not serve copyrighted template files or full article text."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "service": "TemplateLab Metadata API",
        "docs": "/docs",
        "endpoints": [
            "/templates",
            "/templates/{id}",
            "/categories",
            "/categories/{id}/templates",
            "/formats",
            "/search?q=",
            "/stats",
            "/crawl/status",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    from app.config import get_settings

    s = get_settings()
    uvicorn.run("app.main:app", host=s.api_host, port=s.api_port, reload=False)
