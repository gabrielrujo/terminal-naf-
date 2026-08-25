import json
import os
import tempfile
import unittest
from pathlib import Path

from terminal_naf import create_app
from terminal_naf.database import get_db
from terminal_naf.services.usuarios import criar_usuario, seed_demo_data


class TerminalNafV2TestCase(unittest.TestCase):
    def setUp(self):
        arquivo, self.database_path = tempfile.mkstemp(suffix=".db")
        os.close(arquivo)
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": self.database_path,
                "SECRET_KEY": "chave-de-teste",
                "CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            seed_demo_data()

    def tearDown(self):
        os.unlink(self.database_path)

    def query_one(self, sql, params=()):
        with self.app.app_context():
            return get_db().execute(sql, params).fetchone()

    def login(self, usuario="atendente", senha="atendente123"):
        return self.client.post("/login", data={"usuario": usuario, "senha": senha})

    def criar_atendimento(self, codigo="MEI"):
        servico = self.query_one("SELECT id FROM servicos WHERE codigo = ?", (codigo,))
        response = self.client.post("/atendimento/criar", data={"servico_id": servico["id"]})
        self.assertEqual(response.status_code, 302)
        protocolo = response.headers["Location"].rsplit("/", 1)[-1]
        registro = self.query_one(
            "SELECT * FROM atendimentos WHERE protocolo = ?", (protocolo,)
        )
        return registro

    def test_confirmacao_de_servico_nao_cria_atendimento(self):
        servico = self.query_one("SELECT id FROM servicos WHERE codigo = 'MEI'")
        response = self.client.post(
            "/atendimento/confirmar", data={"servico_id": servico["id"]}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.query_one("SELECT COUNT(*) AS n FROM atendimentos")["n"], 0)

    def test_novo_atendimento_nasce_aguardando_com_senha_sequencial(self):
        primeiro = self.criar_atendimento()
        segundo = self.criar_atendimento("CPF")
        self.assertEqual(primeiro["status"], "AGUARDANDO")
        self.assertEqual(primeiro["senha"], "A001")
        self.assertEqual(segundo["senha"], "A002")
        self.assertRegex(primeiro["protocolo"], r"^NAF-\d{8}-0001$")

    def test_iniciar_muda_estado_e_registra_responsavel(self):
        atendimento = self.criar_atendimento()
        self.login()
        response = self.client.post(f"/atendente/atendimentos/{atendimento['id']}/iniciar")
        self.assertEqual(response.status_code, 302)
        atualizado = self.query_one(
            "SELECT status, atendente_id, iniciado_em FROM atendimentos WHERE id = ?",
            (atendimento["id"],),
        )
        self.assertEqual(atualizado["status"], "EM_ATENDIMENTO")
        self.assertIsNotNone(atualizado["atendente_id"])
        self.assertIsNotNone(atualizado["iniciado_em"])

    def test_concluir_diretamente_e_proibido(self):
        atendimento = self.criar_atendimento()
        self.login()
        self.client.post(f"/atendente/atendimentos/{atendimento['id']}/concluir")
        atualizado = self.query_one(
            "SELECT status, concluido_em FROM atendimentos WHERE id = ?", (atendimento["id"],)
        )
        self.assertEqual(atualizado["status"], "AGUARDANDO")
        self.assertIsNone(atualizado["concluido_em"])

    def test_avaliar_aguardando_e_proibido(self):
        atendimento = self.criar_atendimento()
        response = self.client.post(
            f"/avaliacao/{atendimento['protocolo']}", data={"nota": "5"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.query_one("SELECT COUNT(*) AS n FROM avaliacoes")["n"], 0)

    def test_fluxo_concluido_permite_uma_unica_avaliacao(self):
        atendimento = self.criar_atendimento()
        self.login()
        self.client.post(f"/atendente/atendimentos/{atendimento['id']}/iniciar")
        self.client.post(f"/atendente/atendimentos/{atendimento['id']}/concluir")

        concluido = self.query_one(
            "SELECT status, iniciado_em, concluido_em FROM atendimentos WHERE id = ?",
            (atendimento["id"],),
        )
        self.assertEqual(concluido["status"], "CONCLUIDO")
        self.assertIsNotNone(concluido["iniciado_em"])
        self.assertIsNotNone(concluido["concluido_em"])

        self.client.post("/logout")
        response = self.client.post(
            f"/avaliacao/{atendimento['protocolo']}", data={"nota": "5"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Obrigado! Sua avaliação foi registrada".encode(), response.data)
        self.client.post(f"/avaliacao/{atendimento['protocolo']}", data={"nota": "2"})
        avaliacao = self.query_one(
            "SELECT COUNT(*) AS n, MIN(nota) AS nota FROM avaliacoes WHERE atendimento_id = ?",
            (atendimento["id"],),
        )
        self.assertEqual(avaliacao["n"], 1)
        self.assertEqual(avaliacao["nota"], 5)

    def test_equipe_nao_pode_avaliar_em_nome_do_cidadao(self):
        atendimento = self.criar_atendimento()
        self.login()
        self.client.post(f"/atendente/atendimentos/{atendimento['id']}/iniciar")
        self.client.post(f"/atendente/atendimentos/{atendimento['id']}/concluir")
        response = self.client.post(
            f"/avaliacao/{atendimento['protocolo']}", data={"nota": "5"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/atendente", response.headers["Location"])
        self.assertEqual(self.query_one("SELECT COUNT(*) AS n FROM avaliacoes")["n"], 0)

    def test_cancelado_nao_pode_ser_avaliado(self):
        atendimento = self.criar_atendimento()
        self.login()
        self.client.post(f"/atendente/atendimentos/{atendimento['id']}/cancelar")
        response = self.client.post(
            f"/avaliacao/{atendimento['protocolo']}", data={"nota": "5"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.query_one("SELECT status FROM atendimentos WHERE id = ?", (atendimento["id"],))[
                "status"
            ],
            "CANCELADO",
        )

    def test_areas_internas_exigem_login_e_perfil(self):
        for url in ("/atendente", "/admin", "/admin/usuarios", "/admin/servicos"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

        self.login()
        self.assertEqual(self.client.get("/atendente").status_code, 200)
        self.assertEqual(self.client.get("/admin").status_code, 403)

    def test_dashboard_contabiliza_fluxo_corretamente(self):
        atendimento = self.criar_atendimento()
        self.login()
        self.client.post(f"/atendente/atendimentos/{atendimento['id']}/iniciar")
        self.client.post(f"/atendente/atendimentos/{atendimento['id']}/concluir")
        self.client.post("/logout")
        self.client.post(f"/avaliacao/{atendimento['protocolo']}", data={"nota": "5"})

        self.login("admin", "admin123")
        response = self.client.get("/admin?periodo=total")
        self.assertEqual(response.status_code, 200)
        for texto in ("Senhas emitidas", "Concluídos", "5.0", "MEI"):
            self.assertIn(texto.encode(), response.data)

    def test_chat_troca_mensagens_e_registra_leitura(self):
        atendimento = self.criar_atendimento()
        cidadao = self.client
        equipe = self.app.test_client()
        equipe.post("/login", data={"usuario": "atendente", "senha": "atendente123"})
        equipe.post(f"/atendente/atendimentos/{atendimento['id']}/iniciar")
        painel = equipe.get("/atendente")
        self.assertEqual(painel.status_code, 200)
        self.assertIn(b"Chat com o cidad", painel.data)

        resposta = cidadao.post(
            f"/api/public/chat/{atendimento['protocolo']}/mensagens",
            data={"conteudo": "Preciso separar algum documento?"},
        )
        self.assertEqual(resposta.status_code, 201)
        mensagem_cidadao = resposta.get_json()["mensagem"]
        self.assertEqual(mensagem_cidadao["autor_tipo"], "CIDADAO")

        consulta_equipe = equipe.get(
            f"/atendente/api/atendimentos/{atendimento['id']}/mensagens"
        )
        self.assertEqual(consulta_equipe.status_code, 200)
        self.assertEqual(
            consulta_equipe.get_json()["mensagens"][0]["conteudo"],
            "Preciso separar algum documento?",
        )

        consulta_cidadao = cidadao.get(
            f"/api/public/chat/{atendimento['protocolo']}/mensagens"
        )
        self.assertGreaterEqual(
            consulta_cidadao.get_json()["lido_ate"], mensagem_cidadao["id"]
        )

        resposta_equipe = equipe.post(
            f"/atendente/api/atendimentos/{atendimento['id']}/mensagens",
            data={"conteudo": "Sim. Separe apenas os documentos solicitados na orientação."},
        )
        self.assertEqual(resposta_equipe.status_code, 201)
        mensagem_equipe = resposta_equipe.get_json()["mensagem"]
        self.assertEqual(mensagem_equipe["autor_tipo"], "ATENDENTE")
        self.assertEqual(mensagem_equipe["autor_nome"], "Atendente Demonstração")

        mensagens = cidadao.get(
            f"/api/public/chat/{atendimento['protocolo']}/mensagens"
        ).get_json()["mensagens"]
        self.assertEqual([item["autor_tipo"] for item in mensagens], ["CIDADAO", "ATENDENTE"])

        leitura_equipe = equipe.get(
            f"/atendente/api/atendimentos/{atendimento['id']}/mensagens"
        ).get_json()
        self.assertGreaterEqual(leitura_equipe["lido_ate"], mensagem_equipe["id"])
        self.assertEqual(self.query_one("SELECT COUNT(*) AS n FROM mensagens")["n"], 2)

    def test_chat_so_permite_envio_durante_atendimento(self):
        atendimento = self.criar_atendimento()
        cidadao = self.client
        equipe = self.app.test_client()

        aguardando = cidadao.post(
            f"/api/public/chat/{atendimento['protocolo']}/mensagens",
            data={"conteudo": "Mensagem antes do início"},
        )
        self.assertEqual(aguardando.status_code, 409)

        equipe.post("/login", data={"usuario": "atendente", "senha": "atendente123"})
        equipe.post(f"/atendente/atendimentos/{atendimento['id']}/iniciar")
        durante = cidadao.post(
            f"/api/public/chat/{atendimento['protocolo']}/mensagens",
            data={"conteudo": "Mensagem durante o atendimento"},
        )
        self.assertEqual(durante.status_code, 201)
        equipe.post(f"/atendente/atendimentos/{atendimento['id']}/concluir")

        encerrado = cidadao.post(
            f"/api/public/chat/{atendimento['protocolo']}/mensagens",
            data={"conteudo": "Mensagem depois da conclusão"},
        )
        self.assertEqual(encerrado.status_code, 409)
        consulta = cidadao.get(
            f"/api/public/chat/{atendimento['protocolo']}/mensagens"
        )
        self.assertEqual(consulta.status_code, 200)
        self.assertFalse(consulta.get_json()["aberto"])
        self.assertEqual(len(consulta.get_json()["mensagens"]), 1)

    def test_chat_publico_exige_codigo_em_outro_dispositivo(self):
        atendimento = self.criar_atendimento()
        pagina = self.client.get(f"/protocolo/{atendimento['protocolo']}")
        marcador = b'data-chat-access-code="'
        inicio = pagina.data.index(marcador) + len(marcador)
        codigo = pagina.data[inicio : pagina.data.index(b'"', inicio)].decode()
        self.assertEqual(len(codigo), 8)

        visitante = self.app.test_client()
        url_api = f"/api/public/chat/{atendimento['protocolo']}/mensagens"
        self.assertEqual(visitante.get(url_api).status_code, 403)
        visitante.post(
            f"/protocolo/{atendimento['protocolo']}/autorizar-chat",
            data={"codigo_chat": "INVALIDO"},
        )
        self.assertEqual(visitante.get(url_api).status_code, 403)
        visitante.post(
            f"/protocolo/{atendimento['protocolo']}/autorizar-chat",
            data={"codigo_chat": codigo.lower()},
        )
        self.assertEqual(visitante.get(url_api).status_code, 200)

    def test_chat_impede_acesso_de_outro_atendente(self):
        atendimento = self.criar_atendimento()
        responsavel = self.app.test_client()
        responsavel.post(
            "/login", data={"usuario": "atendente", "senha": "atendente123"}
        )
        responsavel.post(f"/atendente/atendimentos/{atendimento['id']}/iniciar")
        with self.app.app_context():
            criar_usuario(
                "Segundo Atendente", "atendente2", "atendente456", "ATENDENTE"
            )

        outro = self.app.test_client()
        outro.post(
            "/login", data={"usuario": "atendente2", "senha": "atendente456"}
        )
        url = f"/atendente/api/atendimentos/{atendimento['id']}/mensagens"
        self.assertEqual(outro.get(url).status_code, 403)
        self.assertEqual(
            outro.post(url, data={"conteudo": "Não deveria enviar"}).status_code,
            403,
        )

    def test_chat_valida_conteudo_da_mensagem(self):
        atendimento = self.criar_atendimento()
        equipe = self.app.test_client()
        equipe.post("/login", data={"usuario": "atendente", "senha": "atendente123"})
        equipe.post(f"/atendente/atendimentos/{atendimento['id']}/iniciar")
        url = f"/api/public/chat/{atendimento['protocolo']}/mensagens"
        self.assertEqual(self.client.post(url, data={"conteudo": "   "}).status_code, 400)
        self.assertEqual(
            self.client.post(url, data={"conteudo": "x" * 1001}).status_code,
            400,
        )
        self.assertEqual(self.query_one("SELECT COUNT(*) AS n FROM mensagens")["n"], 0)


class CsrfV2TestCase(unittest.TestCase):
    def test_post_sem_token_e_rejeitado(self):
        arquivo, database_path = tempfile.mkstemp(suffix=".db")
        os.close(arquivo)
        try:
            app = create_app(
                {"TESTING": True, "DATABASE": database_path, "SECRET_KEY": "csrf-test"}
            )
            response = app.test_client().post(
                "/login", data={"usuario": "qualquer", "senha": "qualquer"}
            )
            self.assertEqual(response.status_code, 400)
        finally:
            os.unlink(database_path)


class VercelPreviewV2TestCase(unittest.TestCase):
    def test_configuracao_inclui_recursos_da_aplicacao_na_funcao(self):
        projeto = Path(__file__).resolve().parent.parent
        configuracao = json.loads((projeto / "vercel.json").read_text())
        self.assertEqual(
            configuracao["functions"]["index.py"]["includeFiles"],
            "terminal_naf/**",
        )
        self.assertTrue(
            (projeto / "terminal_naf/templates/cidadao/index.html").is_file()
        )
        self.assertFalse((projeto / "terminal_naf/templates/public").exists())

    def test_preview_usa_banco_efemero_e_cria_contas_demo(self):
        arquivo, database_path = tempfile.mkstemp(suffix=".db")
        os.close(arquivo)
        try:
            app = create_app(
                {
                    "TESTING": True,
                    "DATABASE": None,
                    "IS_VERCEL": True,
                    "VERCEL_ENV": "preview",
                    "VERCEL_EPHEMERAL_DEMO": True,
                    "VERCEL_PREVIEW_DATABASE": database_path,
                    "SECRET_KEY": "preview-test",
                    "CSRF_ENABLED": False,
                }
            )
            self.assertEqual(app.config["DATABASE"], database_path)
            response = app.test_client().post(
                "/login", data={"usuario": "atendente", "senha": "atendente123"}
            )
            self.assertEqual(response.status_code, 302)
            with app.app_context():
                usuarios = get_db().execute(
                    "SELECT COUNT(*) AS n FROM usuarios"
                ).fetchone()["n"]
            self.assertEqual(usuarios, 2)
        finally:
            os.unlink(database_path)

    def test_producao_vercel_e_bloqueada_com_sqlite(self):
        with self.assertRaisesRegex(RuntimeError, "SQLite local não é persistente"):
            create_app(
                {
                    "TESTING": True,
                    "DATABASE": None,
                    "IS_VERCEL": True,
                    "VERCEL_ENV": "production",
                }
            )

    def test_producao_vercel_permite_demo_efemera_com_opt_in(self):
        arquivo, database_path = tempfile.mkstemp(suffix=".db")
        os.close(arquivo)
        try:
            app = create_app(
                {
                    "TESTING": True,
                    "DATABASE": None,
                    "IS_VERCEL": True,
                    "VERCEL_ENV": "production",
                    "VERCEL_EPHEMERAL_DEMO": True,
                    "VERCEL_PREVIEW_DATABASE": database_path,
                    "SECRET_KEY": "production-preview-test",
                }
            )
            self.assertEqual(app.config["DATABASE"], database_path)
        finally:
            os.unlink(database_path)


if __name__ == "__main__":
    unittest.main()
