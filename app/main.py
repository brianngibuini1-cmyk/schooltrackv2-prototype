"""FastAPI application and JSON API for SchoolTrack.

Local run:
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8020

Deployment uses the same module with ``DATABASE_URL`` pointing at PostgreSQL.
See DEPLOYMENT.md for the Render and demo-safety setup.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .config import (
    APP_NAME,
    CURRENCY_CODE,
    CURRENCY_SYMBOL,
    DEMO_WARNING,
    SCHOOL_NAME,
    SCHOOL_SUBTITLE,
    STATIC_DIR,
    demo_mode_enabled,
    demo_writes_enabled,
    max_request_bytes,
    rate_limit_window_seconds,
    rate_limit_writes,
    seed_demo_enabled,
    trust_proxy_headers,
)
from .db import Connection, Database, database_from_env, is_empty
from .errors import DomainError, NotFoundError
from .schemas import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    PAYMENT_METHOD_LABELS,
    PAYMENT_METHOD_ORDER,
    STATUS_LABELS,
    STATUS_ORDER,
    PurchaseCreate,
    PurchaseStatusUpdate,
    SupplierCreate,
)
from .security import (
    BodySizeLimitMiddleware,
    DemoGuardMiddleware,
    SecurityHeadersMiddleware,
    SlidingWindowRateLimiter,
)
from .seed import seed_demo_data
from .services import (
    PurchaseFilters,
    create_purchase,
    create_supplier,
    dashboard,
    export_purchases_csv,
    get_purchase,
    get_supplier,
    list_purchases,
    list_suppliers,
    next_reference_preview,
    report,
    update_purchase_status,
)

logger = logging.getLogger("schooltrack")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    database: Database = app.state.database
    database.init_schema()
    logger.info("Database schema ready (%s).", database.label)
    if app.state.demo_mode and database.is_sqlite:
        logger.warning(
            "DEMO_MODE is using SQLite. On a hosting platform this file may be "
            "ephemeral; set DATABASE_URL for a persistent public demo."
        )

    if app.state.seed_demo and is_empty(database):
        summary = seed_demo_data(database)
        if summary["seeded"]:
            logger.info(
                "Demo data created with %s purchases and %s suppliers (%s).",
                summary["purchases"],
                summary["suppliers"],
                database.label,
            )
    yield


def get_db(request: Request):
    """One request-scoped connection, always closed afterwards."""

    conn: Connection = request.app.state.database.connect()
    try:
        yield conn
    finally:
        conn.close()


def _validation_fields(exc: RequestValidationError) -> dict[str, str]:
    fields: dict[str, str] = {}
    for error in exc.errors():
        location = [
            str(part)
            for part in error.get("loc", ())
            if part not in {"body", "query", "path"}
        ]
        key = ".".join(location) or "form"
        message = error.get("msg", "Invalid value.")
        message = message.removeprefix("Value error, ")
        fields.setdefault(key, message)
    return fields


def _filters(
    *,
    search: str = "",
    category: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    supplier_id: int | None = None,
) -> PurchaseFilters:
    if date_from and date_to and date_from > date_to:
        raise DomainError(
            "The 'from' date must be on or before the 'to' date.", status_code=422
        )
    return PurchaseFilters(
        search=search,
        category=category,
        status=status,
        date_from=date_from,
        date_to=date_to,
        supplier_id=supplier_id,
    )


def create_app(
    db_path: str | Path | None = None,
    seed_demo: bool | None = None,
    *,
    database_url: str | None = None,
    database: Database | None = None,
    demo_mode: bool | None = None,
    writes_enabled: bool | None = None,
    request_limit_bytes: int | None = None,
    write_rate_limit: int | None = None,
    write_rate_window: int | None = None,
    trust_proxy: bool | None = None,
) -> FastAPI:
    """Build the app with injectable configuration for tests and deployments."""

    if database is not None and (db_path is not None or database_url is not None):
        raise ValueError("Pass either database, db_path or database_url, not several.")
    if db_path is not None and database_url is not None:
        raise ValueError("Pass either db_path or database_url, not both.")

    if database is None:
        if db_path is not None:
            database = Database.sqlite(Path(db_path))
        elif database_url is not None:
            database = Database.from_url(database_url)
        else:
            database = database_from_env()

    is_demo = demo_mode_enabled() if demo_mode is None else demo_mode
    can_write = demo_writes_enabled(is_demo) if writes_enabled is None else writes_enabled
    body_limit = request_limit_bytes or max_request_bytes()
    rate_limit = write_rate_limit or rate_limit_writes()
    rate_window = write_rate_window or rate_limit_window_seconds()
    proxy_headers = trust_proxy_headers() if trust_proxy is None else trust_proxy

    app = FastAPI(
        title="SchoolTrack API",
        version=__version__,
        description=(
            "School purchase and expenditure prototype. "
            "See README.md and DEPLOYMENT.md for configuration."
        ),
        lifespan=_lifespan,
        # Swagger UI loads from a CDN; the product UI is fully self-hosted.
        # The OpenAPI schema remains available locally.
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.database = database
    app.state.seed_demo = seed_demo_enabled() if seed_demo is None else seed_demo
    app.state.demo_mode = is_demo
    app.state.writes_enabled = can_write
    app.state.request_limit_bytes = body_limit
    app.state.rate_limit_writes = rate_limit
    app.state.rate_limit_window = rate_window
    app.state.rate_limiter = (
        SlidingWindowRateLimiter(rate_limit, rate_window)
        if is_demo and can_write
        else None
    )

    app.add_middleware(
        DemoGuardMiddleware,
        demo_mode=is_demo,
        writes_enabled=can_write,
        limiter=app.state.rate_limiter,
        trust_proxy_headers=proxy_headers,
    )
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=body_limit)
    app.add_middleware(SecurityHeadersMiddleware)

    # ------------------------------------------------------------------
    # Error responses (always JSON for /api/*)
    # ------------------------------------------------------------------
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "message": "Some details need attention. Please review the highlighted fields.",
                    "fields": _validation_fields(exc),
                }
            },
        )

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": exc.message, "fields": {}}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, exc: StarletteHTTPException
    ) -> Response:
        if request.url.path.startswith("/api/"):
            detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": {"message": detail, "fields": {}}},
            )
        return await http_exception_handler(request, exc)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> Response:
        logger.exception(
            "Unhandled error while processing %s %s", request.method, request.url.path
        )
        if request.url.path.startswith("/api/") or request.url.path == "/healthz":
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "message": (
                            "Something went wrong on the server. Please try again."
                        ),
                        "fields": {},
                    }
                },
            )
        return PlainTextResponse("Internal Server Error", status_code=500)

    # ------------------------------------------------------------------
    # Readiness / metadata
    # ------------------------------------------------------------------
    @app.get("/api/health")
    def health() -> Response:
        db: Database = app.state.database
        try:
            db.ping()
        except Exception:  # noqa: BLE001 - public response must stay generic
            logger.exception("Database readiness check failed.")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "ready": False,
                    "app": APP_NAME,
                    "version": __version__,
                },
            )
        return JSONResponse(
            content={
                "status": "ok",
                "ready": True,
                "app": APP_NAME,
                "version": __version__,
                "database": db.backend,
                "demo_mode": app.state.demo_mode,
                "writes_enabled": app.state.writes_enabled,
            }
        )

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> Response:
        return health()

    @app.get("/api/meta")
    def meta(db: Connection = Depends(get_db)) -> dict:
        demo_count = db.execute(
            "SELECT COUNT(*) AS n FROM purchases WHERE is_demo = 1"
        ).fetchone()["n"]
        return {
            "app_name": APP_NAME,
            "school_name": SCHOOL_NAME,
            "school_subtitle": SCHOOL_SUBTITLE,
            "version": __version__,
            "today": date.today().isoformat(),
            "currency": CURRENCY_CODE,
            "currency_symbol": CURRENCY_SYMBOL,
            "categories": [
                {"value": key, "label": CATEGORY_LABELS[key]} for key in CATEGORY_ORDER
            ],
            "payment_methods": [
                {"value": key, "label": PAYMENT_METHOD_LABELS[key]}
                for key in PAYMENT_METHOD_ORDER
            ],
            "statuses": [
                {"value": key, "label": STATUS_LABELS[key]} for key in STATUS_ORDER
            ],
            "demo_mode": app.state.demo_mode,
            "writes_enabled": app.state.writes_enabled,
            "demo_warning": DEMO_WARNING,
            "storage_backend": app.state.database.backend,
            "demo_purchase_count": int(demo_count),
        }

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @app.get("/api/dashboard")
    def api_dashboard(
        category: Literal["primary", "jss"] | None = None,
        db: Connection = Depends(get_db),
    ) -> dict:
        return dashboard(db, category)

    # ------------------------------------------------------------------
    # Purchases
    # ------------------------------------------------------------------
    @app.get("/api/purchases/next-reference")
    def api_next_reference(
        purchase_date: date | None = None,
        db: Connection = Depends(get_db),
    ) -> dict:
        target = purchase_date or date.today()
        return {"preview": next_reference_preview(db, target)}

    @app.get("/api/purchases/export.csv")
    def api_export_purchases(
        search: str = Query("", max_length=120),
        category: Literal["primary", "jss"] | None = None,
        status: Literal["pending", "approved", "rejected"] | None = None,
        date_from: date | None = Query(None, alias="from"),
        date_to: date | None = Query(None, alias="to"),
        supplier_id: int | None = Query(None, ge=1),
        db: Connection = Depends(get_db),
    ) -> Response:
        filters = _filters(
            search=search,
            category=category,
            status=status,
            date_from=date_from,
            date_to=date_to,
            supplier_id=supplier_id,
        )
        csv_text = export_purchases_csv(db, filters)
        filename = f"schooltrack-purchases-{date.today():%Y%m%d}.csv"
        return Response(
            content=csv_text,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    @app.get("/api/purchases")
    def api_list_purchases(
        search: str = Query("", max_length=120),
        category: Literal["primary", "jss"] | None = None,
        status: Literal["pending", "approved", "rejected"] | None = None,
        date_from: date | None = Query(None, alias="from"),
        date_to: date | None = Query(None, alias="to"),
        supplier_id: int | None = Query(None, ge=1),
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1, le=100),
        db: Connection = Depends(get_db),
    ) -> dict:
        filters = _filters(
            search=search,
            category=category,
            status=status,
            date_from=date_from,
            date_to=date_to,
            supplier_id=supplier_id,
        )
        return list_purchases(db, filters, page=page, per_page=per_page)

    @app.post("/api/purchases", status_code=201)
    def api_create_purchase(
        payload: PurchaseCreate,
        db: Connection = Depends(get_db),
    ) -> dict:
        return create_purchase(db, payload, is_demo=app.state.demo_mode)

    @app.get("/api/purchases/{purchase_id}")
    def api_get_purchase(
        purchase_id: int, db: Connection = Depends(get_db)
    ) -> dict:
        purchase = get_purchase(db, purchase_id)
        if purchase is None:
            raise NotFoundError("Purchase not found.")
        return purchase

    @app.patch("/api/purchases/{purchase_id}/status")
    def api_update_purchase_status(
        purchase_id: int,
        payload: PurchaseStatusUpdate,
        db: Connection = Depends(get_db),
    ) -> dict:
        return update_purchase_status(db, purchase_id, payload.status)

    # ------------------------------------------------------------------
    # Suppliers
    # ------------------------------------------------------------------
    @app.get("/api/suppliers")
    def api_list_suppliers(
        search: str = Query("", max_length=120),
        db: Connection = Depends(get_db),
    ) -> dict:
        items = list_suppliers(db, search)
        return {"items": items, "total": len(items)}

    @app.post("/api/suppliers", status_code=201)
    def api_create_supplier(
        payload: SupplierCreate,
        db: Connection = Depends(get_db),
    ) -> dict:
        return create_supplier(db, payload, is_demo=app.state.demo_mode)

    @app.get("/api/suppliers/{supplier_id}")
    def api_get_supplier(
        supplier_id: int, db: Connection = Depends(get_db)
    ) -> dict:
        supplier = get_supplier(db, supplier_id)
        if supplier is None:
            raise NotFoundError("Supplier not found.")
        return supplier

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------
    @app.get("/api/reports")
    def api_reports(
        date_from: date | None = Query(None, alias="from"),
        date_to: date | None = Query(None, alias="to"),
        category: Literal["primary", "jss"] | None = None,
        status_scope: Literal["approved", "active"] = Query(
            "approved", alias="status"
        ),
        db: Connection = Depends(get_db),
    ) -> dict:
        today = date.today()
        start = date_from or date(today.year, 1, 1)
        end = date_to or today
        filters = _filters(
            category=category,
            status=None,
            date_from=start,
            date_to=end,
        )
        return report(db, filters, status_scope=status_scope)

    # ------------------------------------------------------------------
    # Frontend
    # ------------------------------------------------------------------
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon() -> FileResponse:
        return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")

    return app


app = create_app()
