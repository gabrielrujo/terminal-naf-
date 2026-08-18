"""Consultas consolidadas do painel administrativo."""

from datetime import date, timedelta

from ..database import get_db
from ..models import RegraDeNegocioError


def limites_periodo(periodo, inicio=None, fim=None):
    hoje = date.today()
    if periodo == "hoje":
        return hoje.isoformat(), hoje.isoformat(), "Hoje"
    if periodo == "7dias":
        return (hoje - timedelta(days=6)).isoformat(), hoje.isoformat(), "Últimos 7 dias"
    if periodo == "mes":
        return hoje.replace(day=1).isoformat(), hoje.isoformat(), "Mês atual"
    if periodo == "total":
        return None, None, "Total geral"
    if periodo == "personalizado":
        try:
            inicio_data = date.fromisoformat(inicio or "")
            fim_data = date.fromisoformat(fim or "")
        except ValueError as error:
            raise RegraDeNegocioError("Informe um período válido.") from error
        if inicio_data > fim_data:
            raise RegraDeNegocioError("A data inicial não pode ser posterior à final.")
        return inicio_data.isoformat(), fim_data.isoformat(), "Período personalizado"
    raise RegraDeNegocioError("Filtro de período inválido.")


def _filtro_sql(inicio, fim):
    if inicio is None:
        return "", ()
    return "WHERE substr(a.criado_em, 1, 10) BETWEEN ? AND ?", (inicio, fim)


def obter_dashboard(periodo="hoje", inicio=None, fim=None):
    inicio, fim, rotulo = limites_periodo(periodo, inicio, fim)
    filtro, params = _filtro_sql(inicio, fim)
    db = get_db()
    totais = db.execute(
        f"""
        SELECT
            COUNT(*) AS emitidas,
            SUM(CASE WHEN a.status = 'AGUARDANDO' THEN 1 ELSE 0 END) AS aguardando,
            SUM(CASE WHEN a.status = 'EM_ATENDIMENTO' THEN 1 ELSE 0 END) AS em_atendimento,
            SUM(CASE WHEN a.status = 'CONCLUIDO' THEN 1 ELSE 0 END) AS concluidos,
            SUM(CASE WHEN a.status = 'CANCELADO' THEN 1 ELSE 0 END) AS cancelados,
            AVG(CASE WHEN a.iniciado_em IS NOT NULL
                THEN (julianday(a.iniciado_em) - julianday(a.criado_em)) * 1440 END) AS espera_media,
            AVG(CASE WHEN a.concluido_em IS NOT NULL AND a.iniciado_em IS NOT NULL
                THEN (julianday(a.concluido_em) - julianday(a.iniciado_em)) * 1440 END) AS atendimento_medio
        FROM atendimentos a
        {filtro}
        """,
        params,
    ).fetchone()
    avaliacoes = db.execute(
        f"""
        SELECT AVG(av.nota) AS media, COUNT(av.id) AS quantidade
        FROM atendimentos a
        JOIN avaliacoes av ON av.atendimento_id = a.id
        {filtro}
        """,
        params,
    ).fetchone()
    por_servico = db.execute(
        f"""
        SELECT s.nome, COUNT(a.id) AS quantidade
        FROM atendimentos a
        JOIN servicos s ON s.id = a.servico_id
        {filtro + (' AND' if filtro else ' WHERE')} a.status = 'CONCLUIDO'
        GROUP BY s.id, s.nome
        ORDER BY quantidade DESC, s.nome
        """,
        params,
    ).fetchall()
    return {
        "periodo": periodo,
        "inicio": inicio,
        "fim": fim,
        "rotulo": rotulo,
        "totais": totais,
        "avaliacoes": avaliacoes,
        "por_servico": por_servico,
    }


def resumo_operacao():
    hoje = date.today().isoformat()
    return get_db().execute(
        """
        SELECT
            SUM(CASE WHEN status = 'AGUARDANDO' THEN 1 ELSE 0 END) AS aguardando,
            SUM(CASE WHEN status = 'EM_ATENDIMENTO' THEN 1 ELSE 0 END) AS em_atendimento,
            SUM(CASE WHEN status = 'CONCLUIDO' AND substr(concluido_em, 1, 10) = ?
                THEN 1 ELSE 0 END) AS concluidos_hoje
        FROM atendimentos
        """,
        (hoje,),
    ).fetchone()
