"""Configurações da aplicação, todas substituíveis por variáveis de ambiente."""

import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("NAF_SECRET_KEY", "terminal-naf-v2-apenas-desenvolvimento")
    DATABASE = os.environ.get("NAF_DATABASE")
    BACKUP_DIR = os.environ.get("NAF_BACKUP_DIR")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("NAF_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    CSRF_ENABLED = True
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024
    IS_VERCEL = os.environ.get("VERCEL") == "1"
    VERCEL_ENV = os.environ.get("VERCEL_ENV", "")
    VERCEL_EPHEMERAL_DEMO = IS_VERCEL and (
        VERCEL_ENV in {"preview", "development"}
        or os.environ.get("NAF_ALLOW_EPHEMERAL_VERCEL") == "1"
    )
    VERCEL_PREVIEW_DATABASE = os.environ.get(
        "NAF_VERCEL_PREVIEW_DATABASE", "/tmp/terminal_naf_v2_preview.db"
    )
