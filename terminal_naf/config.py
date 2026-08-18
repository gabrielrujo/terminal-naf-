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
