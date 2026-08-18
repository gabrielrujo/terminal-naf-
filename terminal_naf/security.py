"""Autenticação, autorização e proteção CSRF baseada em sessão."""

import secrets
from functools import wraps
from hmac import compare_digest

from flask import abort, current_app, flash, g, redirect, request, session, url_for

from .database import get_db
from .models import Usuario


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def carregar_usuario():
    g.usuario = None
    usuario_id = session.get("usuario_id")
    if usuario_id is None:
        return

    row = get_db().execute(
        "SELECT id, nome, login, perfil, ativo FROM usuarios WHERE id = ?",
        (usuario_id,),
    ).fetchone()
    if row is None or not row["ativo"]:
        session.clear()
        return
    g.usuario = Usuario.from_row(row)


def validar_csrf():
    if not current_app.config.get("CSRF_ENABLED", True):
        return
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    esperado = session.get("_csrf_token", "")
    recebido = request.form.get("csrf_token", "")
    if not esperado or not recebido or not compare_digest(esperado, recebido):
        abort(400)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.usuario is None:
            flash("Entre com seu usuário para continuar.", "erro")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def roles_required(*perfis):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.usuario.perfil not in perfis:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def init_security(app):
    app.before_request(carregar_usuario)
    app.before_request(validar_csrf)
    app.jinja_env.globals["csrf_token"] = csrf_token
