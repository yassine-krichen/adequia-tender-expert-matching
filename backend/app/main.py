from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.common.exceptions import DomainError, domain_error_handler
from app.common.logging import configure_logging
from app.common.tracing import configure_langsmith_tracing
from app.config.settings import get_settings
from app.features.candidates.router import router as candidates_router
from app.features.matching.router import router as matching_router
from app.features.metrics.router import router as metrics_router
from app.features.reporting.router import router as reporting_router
from app.features.tdrs.router import router as tdrs_router

# Local dev origins only — the dashboard is same-origin in production once
# both are served behind the same domain/proxy (docs/09-devops-cicd.md).
_DEV_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def create_app() -> FastAPI:
    settings = get_settings()  # validates env at startup, fails fast if malformed
    configure_logging(settings.log_level)
    configure_langsmith_tracing(settings)

    app = FastAPI(title="AdéquIA API", version="0.1.0")

    if settings.environment == "development":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=_DEV_ORIGINS,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_exception_handler(DomainError, domain_error_handler)

    app.include_router(candidates_router)
    app.include_router(tdrs_router)
    app.include_router(matching_router)
    app.include_router(reporting_router)
    app.include_router(metrics_router)

    return app


app = create_app()
