import os
import tempfile
import unittest

from terminal_naf import create_app
from terminal_naf.database import get_db
from terminal_naf.services.usuarios import seed_demo_data


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


if __name__ == "__main__":
    unittest.main()
