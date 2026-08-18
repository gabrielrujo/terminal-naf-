"""Application factory do Terminal NAF V2."""

from datetime import datetime
from pathlib import Path

from flask import Flask, g, render_template

from . import database
from .cli import register_cli
from .config import Config
from .security import init_security
from .services.catalogo import garantir_servicos_iniciais


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config.get("DATABASE"):
        app.config["DATABASE"] = str(Path(app.instance_path) / "terminal_naf_v2.db")
    if not app.config.get("BACKUP_DIR"):
        app.config["BACKUP_DIR"] = str(Path(app.root_path).parent / "backups")

    database.init_app(app)
    init_security(app)
    register_cli(app)

    from .routes.admin import bp as admin_bp
    from .routes.atendente import bp as atendente_bp
    from .routes.auth import bp as auth_bp
    from .routes.public import bp as public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(atendente_bp)
    app.register_blueprint(admin_bp)

    register_template_helpers(app)
    register_error_handlers(app)

    with app.app_context():
        database.init_db()
        garantir_servicos_iniciais()

    return app


def register_template_helpers(app):
    @app.template_filter("data_hora")
    def data_hora(value):
        if not value:
            return "—"
        try:
            return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
        except (TypeError, ValueError):
            return value

    @app.template_filter("hora")
    def hora(value):
        if not value:
            return "—"
        try:
            return datetime.fromisoformat(value).strftime("%H:%M")
        except (TypeError, ValueError):
            return value

    @app.template_filter("minutos_desde")
    def minutos_desde(value):
        if not value:
            return 0
        try:
            inicio = datetime.fromisoformat(value)
            agora = datetime.now().astimezone()
            if inicio.tzinfo is None:
                agora = agora.replace(tzinfo=None)
            return max(0, int((agora - inicio).total_seconds() // 60))
        except (TypeError, ValueError):
            return 0

    @app.template_filter("duracao_minutos")
    def duracao_minutos(inicio, fim):
        if not inicio or not fim:
            return 0
        try:
            return max(
                0,
                int(
                    (
                        datetime.fromisoformat(fim) - datetime.fromisoformat(inicio)
                    ).total_seconds()
                    // 60
                ),
            )
        except (TypeError, ValueError):
            return 0

    @app.context_processor
    def contexto_global():
        return {
            "usuario_atual": getattr(g, "usuario", None),
            "status_rotulos": {
                "AGUARDANDO": "Aguardando atendimento",
                "EM_ATENDIMENTO": "Em atendimento",
                "CONCLUIDO": "Atendimento concluído",
                "CANCELADO": "Atendimento cancelado",
            },
        }


def register_error_handlers(app):
    def render_error(codigo, titulo, mensagem):
        template = "errors/admin.html" if getattr(g, "usuario", None) else "errors/public.html"
        return render_template(template, codigo=codigo, titulo=titulo, mensagem=mensagem), codigo

    @app.errorhandler(400)
    def bad_request(_error):
        return render_error(400, "Solicitação inválida", "Confira os dados e tente novamente.")

    @app.errorhandler(403)
    def forbidden(_error):
        return render_error(403, "Acesso não autorizado", "Seu perfil não possui acesso a esta área.")

    @app.errorhandler(404)
    def not_found(_error):
        return render_error(404, "Página não encontrada", "O endereço informado não existe.")

    @app.errorhandler(500)
    def internal_error(_error):
        if "db_v2" in g:
            g.db_v2.rollback()
        return render_error(500, "Não foi possível concluir", "Tente novamente em alguns instantes.")
