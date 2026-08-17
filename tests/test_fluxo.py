import os
import tempfile
import unittest

from app import app, get_db, init_db


class FluxoAtendimentoTestCase(unittest.TestCase):
    def setUp(self):
        arquivo, self.caminho_banco = tempfile.mkstemp(suffix=".db")
        os.close(arquivo)
        app.config.update(TESTING=True, DATABASE=self.caminho_banco, SECRET_KEY="teste")
        with app.app_context():
            init_db()
        self.client = app.test_client()

    def tearDown(self):
        os.unlink(self.caminho_banco)

    def consultar(self, comando, parametros=()):
        with app.app_context():
            return get_db().execute(comando, parametros).fetchone()

    def criar_coordenador(self):
        return self.client.post(
            "/configuracao-inicial",
            data={"nome": "Coordenação", "login": "coord", "senha": "segredo123"},
        )

    def test_fluxo_so_conta_depois_da_conclusao(self):
        self.criar_coordenador()

        resposta = self.client.post("/atendimento", data={"servico": "mei"})
        self.assertEqual(resposta.status_code, 302)
        protocolo = resposta.headers["Location"].rsplit("/", 1)[-1]

        registro = self.consultar(
            "SELECT id, status, resolvido FROM atendimentos WHERE protocolo = ?",
            (protocolo,),
        )
        self.assertEqual(registro["status"], "aguardando")
        self.assertEqual(registro["resolvido"], 0)

        resposta = self.client.get(f"/avaliacao/{protocolo}")
        self.assertEqual(resposta.status_code, 302)

        self.client.post(f"/atendimentos/{registro['id']}/iniciar")
        em_atendimento = self.consultar(
            "SELECT status, resolvido FROM atendimentos WHERE id = ?", (registro["id"],)
        )
        self.assertEqual(em_atendimento["status"], "em_atendimento")
        self.assertEqual(em_atendimento["resolvido"], 0)

        resposta = self.client.post(f"/atendimentos/{registro['id']}/concluir")
        self.assertEqual(resposta.status_code, 302)
        concluido = self.consultar(
            "SELECT status, resolvido, concluido_em FROM atendimentos WHERE id = ?",
            (registro["id"],),
        )
        self.assertEqual(concluido["status"], "concluido")
        self.assertEqual(concluido["resolvido"], 1)
        self.assertIsNotNone(concluido["concluido_em"])

        resposta = self.client.post(f"/avaliacao/{protocolo}", data={"nota": "5"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            self.consultar("SELECT nota FROM avaliacoes WHERE protocolo = ?", (protocolo,))["nota"],
            5,
        )

    def test_dashboard_exige_coordenador(self):
        resposta = self.client.get("/dashboard")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/login", resposta.headers["Location"])

        self.criar_coordenador()
        resposta = self.client.get("/dashboard")
        self.assertEqual(resposta.status_code, 200)


if __name__ == "__main__":
    unittest.main()
