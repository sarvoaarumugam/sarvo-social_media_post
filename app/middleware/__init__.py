"""Single place that registers all middleware (incl. CORS) onto the app."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.middleware.request_context import RequestContextMiddleware


def register_middleware(app: FastAPI) -> None:
    settings = get_settings()

    # Note: middleware runs in reverse registration order, so CORS is added last
    # to ensure it wraps everything (incl. error responses) on the way out.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
