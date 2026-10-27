"""FastAPI application factory and feature-router composition."""
from contextlib import asynccontextmanager
import threading
from fastapi import FastAPI
from app.api import pages
from app.features.ad_review import routes as ad_review
from app.features.chat import routes as chat
from app.features.documents import routes as documents
from app.features.reports import routes as reports
from app.features.status import routes as status


def create_app(*, warm_models: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if warm_models:
            from app.bootstrap import get_ready
            threading.Thread(target=get_ready, daemon=True).start()
        yield

    application = FastAPI(title="Aida", lifespan=lifespan)
    for feature in (pages, chat, ad_review, documents, reports, status):
        application.include_router(feature.router)
    return application


app = create_app()


def run():
    import uvicorn
    from app.core.config import PORT
    print(f"Open http://127.0.0.1:{PORT} in your browser")
    uvicorn.run(app, host="127.0.0.1", port=PORT)
