"""Painel operacional compartilhado por atendentes e administradores."""

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ..models import Perfil, RegraDeNegocioError
from ..security import roles_required
from ..services.atendimentos import (
    cancelar_atendimento,
    chamar_atendimento,
    concluir_atendimento,
    iniciar_atendimento,
    listar_atendimentos,
    listar_fila,
)
from ..services.indicadores import resumo_operacao


bp = Blueprint("atendente", __name__, url_prefix="/atendente")
equipe_required = roles_required(Perfil.ATENDENTE, Perfil.ADMIN)


@bp.get("")
@equipe_required
def painel():
    fila = listar_fila()
    atual = next(
        (
            item
            for item in fila
            if item["status"] == "EM_ATENDIMENTO" and item["atendente_id"] == g.usuario.id
        ),
        None,
    )
    chamado = next(
        (
            item
            for item in fila
            if item["status"] == "AGUARDANDO"
            and item["atendente_id"] == g.usuario.id
            and item["chamado_em"]
        ),
        None,
    )
    return render_template(
        "atendente/painel.html",
        fila=fila,
        atual=atual,
        chamado=chamado,
        resumo=resumo_operacao(),
    )


@bp.get("/atendimentos")
@equipe_required
def meus_atendimentos():
    registros = listar_atendimentos(atendente_id=g.usuario.id)
    return render_template("atendente/atendimentos.html", atendimentos=registros)


def _executar_acao(acao, atendimento_id, mensagem, **kwargs):
    try:
        acao(atendimento_id, g.usuario, **kwargs)
    except RegraDeNegocioError as error:
        flash(str(error), "erro")
    else:
        flash(mensagem, "sucesso")
    return redirect(url_for("atendente.painel"))


@bp.post("/atendimentos/<int:atendimento_id>/chamar")
@equipe_required
def chamar(atendimento_id):
    return _executar_acao(chamar_atendimento, atendimento_id, "Senha chamada.")


@bp.post("/atendimentos/<int:atendimento_id>/iniciar")
@equipe_required
def iniciar(atendimento_id):
    return _executar_acao(iniciar_atendimento, atendimento_id, "Atendimento iniciado.")


@bp.post("/atendimentos/<int:atendimento_id>/concluir")
@equipe_required
def concluir(atendimento_id):
    return _executar_acao(
        concluir_atendimento,
        atendimento_id,
        "Atendimento concluído. O cidadão já pode avaliar pelo protocolo.",
    )


@bp.post("/atendimentos/<int:atendimento_id>/cancelar")
@equipe_required
def cancelar(atendimento_id):
    return _executar_acao(
        cancelar_atendimento,
        atendimento_id,
        "Atendimento cancelado.",
        motivo=request.form.get("motivo", ""),
    )
