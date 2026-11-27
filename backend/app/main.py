import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from datetime import datetime
from app.core.auth import router as auth_router, session_for, valid_origin, allow_expensive_request
from app.api.research import router as research_router
from app.api.extensions import router as extensions_router
from app.core.config import request_mode, request_as_of

from app.api import base_router
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("skynexus")


def _ingest_loop(interval_s: int) -> None:
    import gc
    from app.services import ingest

    while True:
        summary = ingest.run_cycle()
        logger.info("[ingest] %s", summary)
        gc.collect()
        time.sleep(interval_s)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    logger.info("SkyNexus starting: env=%s data_mode=%s live_ingest=%s",
                settings.ENV, settings.DATA_MODE, settings.LIVE_INGEST)
    if settings.free_demo:
        from app.prepare_hosted_data import verify
        verify()
    yield


app = FastAPI(title="SkyNexus API", version="2.0.0", lifespan=lifespan)
app.include_router(auth_router, prefix="/api")
app.include_router(research_router, prefix="/api")
app.include_router(base_router, prefix="/api")
app.include_router(extensions_router, prefix="/api")

_export_lock = __import__('asyncio').Lock()

from app.services.artifacts import StorageLimitError


@app.exception_handler(StorageLimitError)
async def storage_limit(request, error):
    return JSONResponse({'detail':str(error)},status_code=413)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get('/api/ready')
def readiness():
    from sqlalchemy import text
    from app.core.db import engine
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1 FROM research_sessions LIMIT 0'))
            connection.execute(text('SELECT 1 FROM artifact_objects LIMIT 0'))
        return {'status':'ready','profile':get_settings().HOSTING_PROFILE}
    except Exception:
        return JSONResponse({'status':'unavailable'},status_code=503)


@app.middleware("http")
async def authenticate(request, call_next):
    path = request.url.path
    public_auth=("/api/auth/login","/api/auth/demo","/api/auth/options")
    if path.startswith("/api/") and path not in ("/api/health",'/api/ready',*public_auth):
        user = await __import__('asyncio').to_thread(session_for, request)
        if not user:
            return JSONResponse({"detail":"Sign in required"}, status_code=401)
        request.state.user = user
        if request.method=='POST' and (path.startswith('/api/experiments') or path.startswith('/api/report') or path.startswith('/api/cases')):
            if not allow_expensive_request(user['session_id']):
                return JSONResponse({'detail':'Research request limit reached; retry in five minutes'},status_code=429,headers={'Retry-After':'300'})
        if request.method not in ("GET", "HEAD", "OPTIONS") and not valid_origin(request):
            return JSONResponse({"detail":"Invalid request origin"}, status_code=403)
        if path in ("/api/system/mode", "/api/ingest/live") and request.method == "POST":
            return JSONResponse({"detail":"Collection settings are administrative; use viewer dataset controls."},status_code=403)
        from app.core.capabilities import restricted
        if restricted(path,request.method):
            return JSONResponse({'detail':'This action needs the full local workspace. The hosted demo provides prepared historical replay and cached evaluations.'},status_code=409)
    elif path in public_auth and request.method=='POST' and not valid_origin(request):
        return JSONResponse({"detail":"Invalid request origin"},status_code=403)
    mode = request.query_params.get('data_mode')
    mode_token = request_mode.set(mode if mode in ('live','demo') else None)
    try:
        value=request.query_params.get('as_of')
        asof=datetime.fromisoformat(value.replace('Z','+00:00')) if value else None
        if asof and asof.tzinfo is None: raise ValueError()
    except ValueError:
        request_mode.reset(mode_token)
        return JSONResponse({'detail':'as_of requires an ISO timestamp with timezone'}, status_code=422)
    time_token=request_as_of.set(asof)
    try:
        if get_settings().free_demo and request.method=='POST' and path not in public_auth and path!='/api/auth/logout':
            if _export_lock.locked():return JSONResponse({'detail':'Another demo export is running. Please retry shortly.'},status_code=429,headers={'Retry-After':'5'})
            async with _export_lock:
                return await call_next(request)
        return await call_next(request)
    finally:
        request_mode.reset(mode_token)
        request_as_of.reset(time_token)

# Same-origin deployment keeps cookies and event streams off serverless proxies.
from pathlib import Path
if Path('static/index.html').exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    app.mount('/assets', StaticFiles(directory='static/assets'), name='assets')
    @app.get('/{path:path}')
    def frontend(path: str):
        candidate=(Path('static')/path).resolve()
        root=Path('static').resolve()
        if candidate.is_relative_to(root) and candidate.is_file():return FileResponse(candidate)
        if path.startswith('api/'):return JSONResponse({'detail':'Not found'},status_code=404)
        return FileResponse('static/index.html')
