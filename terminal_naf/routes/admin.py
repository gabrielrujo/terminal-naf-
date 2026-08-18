"""Dashboard e cadastros exclusivos da coordenação."""

import sqlite3

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ..database import get_db
from ..models import Perfil, RegraDeNegocioError
from ..security import roles_required
from ..services.atendimentos import listar_atendimentos
from ..services.catalogo import agora_iso, listar_servicos
from ..services.indicadores import obter_dashboard
from ..services.usuarios import alternar_usuario, criar_usuario, listar_usuarios


bp = Blueprint("admin", __name__, url_prefix="/admin")
admin_required = roles_required(Perfil.ADMIN)


@bp.get("")
@admin_required
def dashboard():
    periodo = request.args.get("periodo", "hoje")
    try:
        indicadores = obter_dashboard(
            periodo,
            request.args.get("inicio"),
            request.args.get("fim"),
        )
    except RegraDeNegocioError as error:
        flash(str(error), "erro")
        indicadores = obter_dashboard("hoje")
    return render_template("admin/dashboard.html", indicadores=indicadores)


@bp.get("/atendimentos")
@admin_required
def atendimentos():
    return render_template(
        "admin/atendimentos.html", atendimentos=listar_atendimentos(limite=500)
    )


@bp.route("/usuarios", methods=["GET", "POST"])
@admin_required
def usuarios():
    if request.method == "POST":
        try:
            criar_usuario(
                request.form.get("nome", ""),
                request.form.get("usuario", ""),
                request.form.get("senha", ""),
                request.form.get("perfil", ""),
            )
        except RegraDeNegocioError as error:
            flash(str(error), "erro")
        else:
            flash("Usuário cadastrado.", "sucesso")
            return redirect(url_for("admin.usuarios"))
    return render_template("admin/usuarios.html", usuarios=listar_usuarios())


@bp.post("/usuarios/<int:usuario_id>/alternar")
@admin_required
def usuario_alternar(usuario_id):
    try:
        alternar_usuario(usuario_id, g.usuario.id)
    except RegraDeNegocioError as error:
        flash(str(error), "erro")
    else:
        flash("Situação do usuário atualizada.", "sucesso")
    return redirect(url_for("admin.usuarios"))


@bp.route("/servicos", methods=["GET", "POST"])
@admin_required
def servicos():
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip().upper()
        nome = request.form.get("nome", "").strip()
        descricao = request.form.get("descricao", "").strip()
        if not codigo or not nome or not descricao:
            flash("Preencha código, nome e descrição.", "erro")
        elif len(codigo) > 12:
            flash("O código deve possuir no máximo 12 caracteres.", "erro")
        else:
            try:
                db = get_db()
                db.execute(
                    """
                    INSERT INTO servicos (codigo, nome, descricao, ativo, criado_em)
                    VALUES (?, ?, ?, 1, ?)
                    """,
                    (codigo, nome, descricao, agora_iso()),
                )
                db.commit()
            except sqlite3.IntegrityError:
                get_db().rollback()
                flash("Já existe um serviço com esse código.", "erro")
            else:
                flash("Serviço cadastrado.", "sucesso")
                return redirect(url_for("admin.servicos"))
    return render_template("admin/servicos.html", servicos=listar_servicos(apenas_ativos=False))


@bp.post("/servicos/<int:servico_id>/alternar")
@admin_required
def servico_alternar(servico_id):
    db = get_db()
    cursor = db.execute(
        "UPDATE servicos SET ativo = CASE ativo WHEN 1 THEN 0 ELSE 1 END WHERE id = ?",
        (servico_id,),
    )
    db.commit()
    flash(
        "Situação do serviço atualizada." if cursor.rowcount else "Serviço não encontrado.",
        "sucesso" if cursor.rowcount else "erro",
    )
    return redirect(url_for("admin.servicos"))


@bp.get("/avaliacoes")
@admin_required
def avaliacoes():
    registros = get_db().execute(
        """
        SELECT av.*, a.senha, a.protocolo, s.nome AS servico_nome
        FROM avaliacoes av
        JOIN atendimentos a ON a.id = av.atendimento_id
        JOIN servicos s ON s.id = a.servico_id
        ORDER BY av.criado_em DESC
        LIMIT 500
        """
    ).fetchall()
    return render_template("admin/avaliacoes.html", avaliacoes=registros)
