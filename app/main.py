import logging
import time
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.rate_limit import limiter

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=0.2,
        send_default_pii=False,
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fotomil")

from app.routes import auth, galleries, images, shares, shared_access, export, labs, orders, lab_portal, lab_applications  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FotoMil API starting up")
    yield
    logger.info("FotoMil API shutting down")


app = FastAPI(
    title="FotoMil API",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000)
    # Skip health check and static file noise
    path = request.url.path
    if path != "/api/health" and not path.startswith("/assets"):
        logger.info(
            "%s %s %s %dms",
            request.method,
            path,
            response.status_code,
            duration,
        )
    return response


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(galleries.router, prefix="/api/galleries", tags=["galleries"])
app.include_router(images.router, prefix="/api", tags=["images"])
app.include_router(shares.router, prefix="/api", tags=["shares"])
app.include_router(shared_access.router, prefix="/api/shared", tags=["shared"])
app.include_router(export.router, prefix="/api", tags=["export"])
app.include_router(labs.router, prefix="/api", tags=["labs"])
app.include_router(orders.router, prefix="/api", tags=["orders"])
app.include_router(lab_portal.router, prefix="/api", tags=["lab-portal"])
app.include_router(lab_applications.router, prefix="/api", tags=["lab-applications"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
