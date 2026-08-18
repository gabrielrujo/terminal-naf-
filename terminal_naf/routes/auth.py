"""Login e encerramento de sessão da equipe."""

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from ..models import Perfil
from ..services.usuarios import autenticar


bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.usuario is not None:
        destino = "admin.dashboard" if g.usuario.perfil == Perfil.ADMIN else "atendente.painel"
        return redirect(url_for(destino))

    if request.method == "POST":
        usuario = autenticar(request.form.get("usuario", ""), request.form.get("senha", ""))
        if usuario is None:
            flash("Usuário ou senha inválidos.", "erro")
        else:
            session.clear()
            session.permanent = True
            session["usuario_id"] = usuario["id"]
            destino = "admin.dashboard" if usuario["perfil"] == Perfil.ADMIN else "atendente.painel"
            return redirect(url_for(destino))
    return render_template("auth/login.html")


@bp.post("/logout")
def logout():
    session.clear()
    flash("Sessão encerrada.", "sucesso")
    return redirect(url_for("public.index"))
