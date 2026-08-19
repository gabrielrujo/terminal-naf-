"""Painel operacional compartilhado por atendentes e administradores."""

from flask import (
    Blueprint,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

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
from ..services.chat import (
    enviar_mensagem,
    listar_mensagens,
    obter_atendimento,
    ultima_mensagem_lida,
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


def _chat_permitido(atendimento_id):
    atendimento = obter_atendimento(atendimento_id)
    if atendimento is None:
        return None, (jsonify({"erro": "Atendimento não encontrado."}), 404)
    if (
        atendimento["atendente_id"] != g.usuario.id
        and g.usuario.perfil != Perfil.ADMIN
    ):
        return None, (
            jsonify({"erro": "Este atendimento pertence a outro atendente."}),
            403,
        )
    return atendimento, None


@bp.get("/api/atendimentos/<int:atendimento_id>/mensagens")
@equipe_required
def mensagens_chat(atendimento_id):
    atendimento, erro = _chat_permitido(atendimento_id)
    if erro:
        return erro
    mensagens = listar_mensagens(
        atendimento_id, "ATENDENTE", request.args.get("depois_de", 0)
    )
    return jsonify(
        {
            "mensagens": mensagens,
            "status": atendimento["status"],
            "aberto": atendimento["status"] == "EM_ATENDIMENTO",
            "lido_ate": ultima_mensagem_lida(atendimento_id, "ATENDENTE"),
        }
    )


@bp.post("/api/atendimentos/<int:atendimento_id>/mensagens")
@equipe_required
def enviar_chat(atendimento_id):
    atendimento, erro = _chat_permitido(atendimento_id)
    if erro:
        return erro
    try:
        mensagem = enviar_mensagem(
            atendimento_id,
            "ATENDENTE",
            request.form.get("conteudo"),
            autor_usuario_id=g.usuario.id,
        )
    except RegraDeNegocioError as error:
        status = 409 if "apenas durante o atendimento" in str(error) else 400
        return jsonify({"erro": str(error)}), status
    return jsonify({"mensagem": mensagem}), 201
