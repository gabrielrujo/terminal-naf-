"""Experiência pública do terminal e avaliação do cidadão."""

from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for

from ..models import RegraDeNegocioError, StatusAtendimento
from ..services.atendimentos import criar_atendimento, obter_por_protocolo, registrar_avaliacao
from ..services.catalogo import MATERIAIS, listar_servicos


bp = Blueprint("public", __name__)


def _servico_ativo(servico_id):
    try:
        servico_id = int(servico_id)
    except (TypeError, ValueError):
        return None
    return next((item for item in listar_servicos() if item["id"] == servico_id), None)


@bp.get("/")
def index():
    return render_template("public/index.html")


@bp.get("/atendimento")
def atendimento():
    return render_template("public/atendimento.html", servicos=listar_servicos())


@bp.post("/atendimento/confirmar")
def confirmar_atendimento():
    servico = _servico_ativo(request.form.get("servico_id"))
    if servico is None:
        flash("Escolha um serviço disponível.", "erro")
        return redirect(url_for("public.atendimento"))
    return render_template("public/confirmar_atendimento.html", servico=servico)


@bp.post("/atendimento/criar")
def criar():
    servico = _servico_ativo(request.form.get("servico_id"))
    if servico is None:
        flash("O serviço selecionado não está disponível.", "erro")
        return redirect(url_for("public.atendimento"))
    try:
        registro = criar_atendimento(servico["id"])
    except RegraDeNegocioError as error:
        flash(str(error), "erro")
        return redirect(url_for("public.atendimento"))
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
    return render_template("public/acompanhar.html")


@bp.get("/protocolo/<protocolo>")
def protocolo(protocolo):
    registro = obter_por_protocolo(protocolo)
    if registro is None:
        abort(404)
    return render_template("public/protocolo.html", atendimento=registro)


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
        return render_template("public/avaliacao.html", atendimento=registro, enviado=True)

    if request.method == "POST":
        try:
            registrar_avaliacao(registro["protocolo"], request.form.get("nota"))
        except RegraDeNegocioError as error:
            flash(str(error), "erro")
        else:
            return render_template("public/avaliacao.html", atendimento=registro, enviado=True)
    return render_template("public/avaliacao.html", atendimento=registro, enviado=False)


@bp.get("/informacoes")
def informacoes():
    return render_template("public/informacoes.html", servicos=listar_servicos())


@bp.get("/materiais")
def materiais():
    return render_template("public/materiais.html", materiais=MATERIAIS)
