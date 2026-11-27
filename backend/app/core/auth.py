"""Provisioned demo login with revocable, hashed server-side sessions."""
import hashlib
import secrets
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel, Field
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models.research import SessionRecord

router = APIRouter(prefix='/auth', tags=['authentication'])
COOKIE = 'skynexus_session'
password_hasher = PasswordHasher()
attempts = defaultdict(deque)

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

def session_for(request):
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    with SessionLocal() as db:
        row = db.get(SessionRecord, digest(token))
        if row and row.expires_at > datetime.now(timezone.utc):
            return {'email': row.email, 'role': 'demo', 'session_id': row.token_hash}
    return None

class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)

def limit_login(request):
    key = request.client.host if request.client else 'unknown'
    now = datetime.now(timezone.utc)
    queue = attempts[key]
    while queue and (now - queue[0]).total_seconds() > 300:
        queue.popleft()
    if len(queue) >= 10:
        raise HTTPException(429, 'Too many attempts. Retry in five minutes.', headers={'Retry-After':'300'})
    queue.append(now)


def issue_session(request,response):
    settings=get_settings();now=datetime.now(timezone.utc)
    old = request.cookies.get(COOKIE)
    token = secrets.token_urlsafe(32)
    with SessionLocal() as db:
        if old:
            previous = db.get(SessionRecord, digest(old))
            if previous: db.delete(previous)
        db.add(SessionRecord(token_hash=digest(token), email=settings.DEMO_EMAIL, expires_at=now+timedelta(hours=8)))
        db.commit()
    response.set_cookie(COOKIE, token, httponly=True, secure=settings.COOKIE_SECURE, samesite='lax', max_age=28800, path='/')
    return {'email': settings.DEMO_EMAIL, 'role': 'demo'}


@router.get('/options')
def options():
    from app.core.capabilities import capabilities
    return {'direct_demo_login':get_settings().DEMO_DIRECT_LOGIN, 'capabilities':capabilities()}


@router.post('/demo')
def direct_demo(request:Request,response:Response):
    if not get_settings().DEMO_DIRECT_LOGIN:raise HTTPException(403,'Direct demo entry is disabled')
    limit_login(request)
    return issue_session(request,response)


@router.post('/login')
def login(body: Credentials, request: Request, response: Response):
    limit_login(request)
    settings = get_settings()
    valid = False
    try:
        valid = password_hasher.verify(settings.DEMO_PASSWORD_HASH, body.password)
    except (VerificationError, InvalidHashError):
        pass
    if body.email.casefold() != settings.DEMO_EMAIL.casefold() or not valid:
        raise HTTPException(401, 'Email or password is incorrect')
    return issue_session(request,response)

@router.get('/me')
def me(request: Request):
    user = session_for(request)
    if not user: raise HTTPException(401, 'Sign in required')
    return {'email':user['email'], 'role':user['role']}

@router.post('/logout')
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        with SessionLocal() as db:
            row = db.get(SessionRecord, digest(token))
            if row: db.delete(row)
            db.commit()
    response.delete_cookie(COOKIE, path='/')
    return {'status':'signed_out'}

def valid_origin(request):
    origin = request.headers.get('origin')
    return not origin or urlparse(origin).netloc == request.headers.get('host') or origin == get_settings().PUBLIC_ORIGIN


def allow_expensive_request(identity, limit=10):
    now=datetime.now(timezone.utc)
    queue=attempts['research:'+identity]
    while queue and (now-queue[0]).total_seconds()>300:queue.popleft()
    if len(queue)>=limit:return False
    queue.append(now)
    return True
