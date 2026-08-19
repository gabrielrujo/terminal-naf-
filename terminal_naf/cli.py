"""Comandos seguros para preparar e reiniciar uma demonstração."""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

import click
from flask import current_app

from .database import get_db, init_db
from .services.catalogo import garantir_servicos_iniciais
from .services.usuarios import seed_demo_data


def register_cli(app):
    app.cli.add_command(seed_demo)
    app.cli.add_command(reset_demo)


@click.command("seed-demo")
def seed_demo():
    """Cria serviços e contas locais de demonstração."""
    init_db()
    garantir_servicos_iniciais()
    admin_password = os.environ.get("NAF_DEMO_ADMIN_PASSWORD", "admin123")
    atendente_password = os.environ.get("NAF_DEMO_ATENDENTE_PASSWORD", "atendente123")
    seed_demo_data(admin_password, atendente_password)
    click.echo("Dados de demonstração preparados.")
    click.echo("Admin: admin")
    click.echo("Atendente: atendente")
    click.echo("As senhas vêm das variáveis NAF_DEMO_* ou dos padrões de desenvolvimento.")


@click.command("reset-demo")
@click.option("--yes", is_flag=True, help="Confirma a limpeza sem pergunta interativa.")
def reset_demo(yes):
    """Faz backup e limpa a operação, preservando usuários e serviços."""
    if not yes and not click.confirm("Fazer backup e limpar os atendimentos da demonstração?"):
        click.echo("Operação cancelada.")
        return

    backup_dir = Path(current_app.config["BACKUP_DIR"])
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"terminal_naf_v2.backup-{timestamp}.db"
    source = get_db()
    source.commit()
    with sqlite3.connect(backup_path) as destination:
        source.backup(destination)

    source.execute("DELETE FROM avaliacoes")
    source.execute("DELETE FROM atendimentos")
    source.execute("DELETE FROM sequencias")
    source.commit()
    click.echo(f"Backup criado em: {backup_path}")
    click.echo(
        "Atendimentos, avaliações e chats removidos; "
        "usuários e serviços foram preservados."
    )
