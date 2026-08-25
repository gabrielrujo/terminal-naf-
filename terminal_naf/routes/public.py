"""Experiência pública do terminal e avaliação do cidadão."""

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..models import RegraDeNegocioError, StatusAtendimento
from ..services.atendimentos import (
    criar_atendimento_com_acesso,
    obter_por_protocolo,
    registrar_avaliacao,
)
from ..services.catalogo import MATERIAIS, listar_servicos
from ..services.chat import (
    enviar_mensagem,
    listar_mensagens,
    ultima_mensagem_lida,
    validar_codigo_acesso,
)


bp = Blueprint("public", __name__)


def _servico_ativo(servico_id):
    try:
        servico_id = int(servico_id)
    except (TypeError, ValueError):
        return None
    return next((item for item in listar_servicos() if item["id"] == servico_id), None)


@bp.get("/")
def index():
    session.pop("chat_atendimento_id", None)
    session.pop("chat_codigo_exibicao", None)
    return render_template("cidadao/index.html")


@bp.get("/atendimento")
def atendimento():
    return render_template("cidadao/atendimento.html", servicos=listar_servicos())


@bp.post("/atendimento/confirmar")
def confirmar_atendimento():
    servico = _servico_ativo(request.form.get("servico_id"))
    if servico is None:
        flash("Escolha um serviço disponível.", "erro")
        return redirect(url_for("public.atendimento"))
    return render_template("cidadao/confirmar_atendimento.html", servico=servico)


@bp.post("/atendimento/criar")
def criar():
    servico = _servico_ativo(request.form.get("servico_id"))
    if servico is None:
        flash("O serviço selecionado não está disponível.", "erro")
        return redirect(url_for("public.atendimento"))
    try:
        registro, codigo_chat = criar_atendimento_com_acesso(servico["id"])
    except RegraDeNegocioError as error:
        flash(str(error), "erro")
        return redirect(url_for("public.atendimento"))
    session["chat_atendimento_id"] = registro["id"]
    session["chat_codigo_exibicao"] = codigo_chat
    return redirect(url_for("public.protocolo", protocolo=registro["protocolo"]))


@bp.route("/acompanhar", methods=["GET", "POST"])
def acompanhar():
    if request.method == "POST":
        protocolo = request.form.get("protocolo", "").strip().upper()
        if not protocolo:
            flash("Informe o protocolo recebido.", "erro")
        elif obter_por_protocolo(protocolo) is None:
            flash("Protocolo não encontrado.", "erro")
        else:
            return redirect(url_for("public.protocolo", protocolo=protocolo))
    return render_template("cidadao/acompanhar.html")


@bp.get("/protocolo/<protocolo>")
def protocolo(protocolo):
    registro = obter_por_protocolo(protocolo)
    if registro is None:
        abort(404)
    chat_autorizado = session.get("chat_atendimento_id") == registro["id"]
    codigo_chat = (
        session.get("chat_codigo_exibicao") if chat_autorizado else None
    )
    resposta = make_response(
        render_template(
            "cidadao/protocolo.html",
            atendimento=registro,
            chat_autorizado=chat_autorizado,
            codigo_chat=codigo_chat,
        )
    )
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


@bp.post("/protocolo/<protocolo>/autorizar-chat")
def autorizar_chat(protocolo):
    registro = validar_codigo_acesso(protocolo, request.form.get("codigo_chat"))
    if registro is None:
        flash(
            "Código do chat inválido. Confira o código recebido com o protocolo.",
            "erro",
        )
    else:
        session["chat_atendimento_id"] = registro["id"]
        session["chat_codigo_exibicao"] = (
            request.form.get("codigo_chat", "").strip().upper()
        )
        flash("Chat liberado neste dispositivo.", "sucesso")
    return redirect(url_for("public.protocolo", protocolo=protocolo.strip().upper()))


def _chat_publico(protocolo):
    registro = obter_por_protocolo(protocolo)
    if registro is None:
        return None, (jsonify({"erro": "Protocolo não encontrado."}), 404)
    if session.get("chat_atendimento_id") != registro["id"]:
        return None, (
            jsonify({"erro": "Informe o código do chat para acessar as mensagens."}),
            403,
        )
    return registro, None


@bp.get("/api/public/chat/<protocolo>/mensagens")
def mensagens_chat_publico(protocolo):
    registro, erro = _chat_publico(protocolo)
    if erro:
        return erro
    mensagens = listar_mensagens(
        registro["id"], "CIDADAO", request.args.get("depois_de", 0)
    )
    return jsonify(
        {
            "mensagens": mensagens,
            "status": registro["status"],
            "aberto": registro["status"] == StatusAtendimento.EM_ATENDIMENTO.value,
            "lido_ate": ultima_mensagem_lida(registro["id"], "CIDADAO"),
        }
    )


@bp.post("/api/public/chat/<protocolo>/mensagens")
def enviar_chat_publico(protocolo):
    registro, erro = _chat_publico(protocolo)
    if erro:
        return erro
    try:
        mensagem = enviar_mensagem(
            registro["id"], "CIDADAO", request.form.get("conteudo")
        )
    except RegraDeNegocioError as error:
        status = 409 if "apenas durante o atendimento" in str(error) else 400
        return jsonify({"erro": str(error)}), status
    return jsonify({"mensagem": mensagem}), 201


@bp.get("/api/public/protocolo/<protocolo>")
def protocolo_status(protocolo):
    registro = obter_por_protocolo(protocolo)
    if registro is None:
        return jsonify({"erro": "Protocolo não encontrado"}), 404
    return jsonify(
        {
            "senha": registro["senha"],
            "protocolo": registro["protocolo"],
            "status": registro["status"],
            "pode_avaliar": (
                registro["status"] == StatusAtendimento.CONCLUIDO
                and registro["avaliacao_nota"] is None
            ),
            "avaliado": registro["avaliacao_nota"] is not None,
        }
    )


@bp.route("/avaliacao/<protocolo>", methods=["GET", "POST"])
def avaliacao(protocolo):
    if g.usuario is not None:
        flash("A avaliação deve ser registrada pelo cidadão no terminal público.", "erro")
        return redirect(url_for("atendente.painel"))
    registro = obter_por_protocolo(protocolo)
    if registro is None:
        abort(404)
    if registro["status"] != StatusAtendimento.CONCLUIDO:
        flash("A avaliação será liberada quando o atendimento for concluído.", "erro")
        return redirect(url_for("public.protocolo", protocolo=registro["protocolo"]))
    if registro["avaliacao_nota"] is not None:
        return render_template("cidadao/avaliacao.html", atendimento=registro, enviado=True)

    if request.method == "POST":
        try:
            registrar_avaliacao(registro["protocolo"], request.form.get("nota"))
        except RegraDeNegocioError as error:
            flash(str(error), "erro")
        else:
            return render_template("cidadao/avaliacao.html", atendimento=registro, enviado=True)
    return render_template("cidadao/avaliacao.html", atendimento=registro, enviado=False)


@bp.get("/informacoes")
def informacoes():
    return render_template("cidadao/informacoes.html", servicos=listar_servicos())


@bp.get("/materiais")
def materiais():
    return render_template("cidadao/materiais.html", materiais=MATERIAIS)
