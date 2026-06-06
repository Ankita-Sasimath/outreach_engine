from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import init_db
from app.routes.pipeline import router as pipeline_router
from app.routes.pipeline_stream import router as pipeline_stream_router



def create_app() -> FastAPI:
    app = FastAPI(title="Outreach Engine")

    # Templates + static assets
    templates = Jinja2Templates(directory="templates")
    app.state.templates = templates
    app.mount("/static", StaticFiles(directory="static"), name="static")

    app.include_router(pipeline_router)
    app.include_router(pipeline_stream_router)


    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    return app


app = create_app()

