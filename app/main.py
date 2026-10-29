"""FastAPI application factory and feature-router composition."""
from contextlib import asynccontextmanager
import threading
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from app.core.config import ROOT
from app.api.documentation import API_DESCRIPTION, TAGS, SWAGGER_PARAMETERS
from app.api import pages
from app.features.ad_review import routes as ad_review
from app.features.chat import routes as chat
from app.features.documents import routes as documents
from app.features.reports import routes as reports
from app.features.status import routes as status
from app.features.macea import routes as macea


def create_app(*, warm_models: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if warm_models:
            from app.bootstrap import get_ready
            threading.Thread(target=get_ready, daemon=True).start()
        yield

    application = FastAPI(
        title="Aida API", version="0.1.0", description=API_DESCRIPTION,
        openapi_tags=TAGS, docs_url=None, redoc_url=None, lifespan=lifespan,
        swagger_ui_parameters=SWAGGER_PARAMETERS,
    )
    application.mount("/docs-assets", StaticFiles(directory=ROOT / "static" / "vendor" / "swagger-ui"), name="swagger-assets")

    @application.get("/docs", include_in_schema=False)
    async def swagger_docs():
        return get_swagger_ui_html(
            openapi_url="/openapi.json", title="Aida API — Swagger UI",
            swagger_js_url="/docs-assets/swagger-ui-bundle.js",
            swagger_css_url="/docs-assets/swagger-ui.css",
            swagger_favicon_url="/docs-assets/favicon.svg",
            swagger_ui_parameters=SWAGGER_PARAMETERS,
        )
    for feature in (pages, chat, ad_review, documents, reports, status, macea):
        application.include_router(feature.router)
    return application


app = create_app()


def run():
    import uvicorn
    from app.core.config import PORT
    print(f"Open http://127.0.0.1:{PORT} in your browser")
    uvicorn.run(app, host="127.0.0.1", port=PORT)
