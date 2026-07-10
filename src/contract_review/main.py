from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from contract_review.api.v1.router import api_router
from contract_review.core.config import get_settings
from contract_review.core.exception_handlers import register_exception_handlers
from contract_review.core.logging import configure_logging
from contract_review.core.middleware import (
    MetricsMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from contract_review.graph.graph_builder import build_contract_review_graph

WEB_DIR = Path(__file__).resolve().parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.contract_review_graph = build_contract_review_graph()
    yield


def render_html(template_name: str, title: str) -> HTMLResponse:
    template = (WEB_DIR / template_name).read_text(encoding="utf-8")
    return HTMLResponse(template.replace("__APP_TITLE__", title))


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "基于 FastAPI、LangChain 与 LangGraph 构建的企业级多源合同智能审查后端。"
            "系统通过外部大语言模型 API 协同多个 Agent，支持合同解析、要素提取、"
            "合规风险识别与修改建议生成。"
        ),
        docs_url=None,
        redoc_url=None,
        openapi_tags=[
            {"name": "系统健康", "description": "用于检查服务是否正常运行的基础接口。"},
            {"name": "合同审查", "description": "上传合同文件并触发 Multi-Agent 智能审查流程。"},
        ],
        lifespan=lifespan,
    )

    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    @app.get("/", include_in_schema=False)
    async def home_page() -> HTMLResponse:
        return render_html("home.html", settings.app_name)

    @app.get("/docs", include_in_schema=False)
    async def docs_page() -> HTMLResponse:
        return render_html("docs.html", settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.rate_limit_per_minute)
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
        )
        for item in schema.get("components", {}).get("schemas", {}).values():
            properties = item.get("properties")
            if isinstance(properties, dict) and "合同文件" in properties and "file" in properties:
                properties.pop("file", None)
                item["required"] = ["合同文件"]
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi
    return app


app = create_app()
