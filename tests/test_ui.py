import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from recruitment.database import Database

ROOT = Path(__file__).resolve().parent.parent


def click(app, label):
    next(button for button in app.button if button.label == label).click().run()
    if app.exception:
        raise AssertionError(str(app.exception))


class StreamlitFlowTests(unittest.TestCase):
    def test_register_job_candidate_chat_report_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ui.db"
            with patch.dict(os.environ, {"DATABASE_PATH": str(path), "DEMO_MODE": "true"}):
                app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
                self.assertFalse(app.exception)
                app.sidebar.radio[0].set_value("Cadastrar vagas").run()
                click(app, "Criar vaga de exemplo para teste")
                self.assertEqual(len(Database(path).list_jobs()), 1)
                app.sidebar.radio[0].set_value("Entrevista").run()
                app.text_input[0].set_value("Candidata de teste")
                app.checkbox[0].check()
                click(app, "Iniciar entrevista")
                self.assertFalse(app.exception)
                # Relato + uma complementar de demonstração + duas padronizadas.
                for response in ["Organizei documentos e ajudei em rotinas administrativas.",
                                 "Organizei pastas da equipe.", "Documentei processos.",
                                 "Combino prioridades e registro pendências."]:
                    app.text_area[0].set_value(response)
                    click(app, "Enviar resposta")
                self.assertTrue(any("Entrevista concluída" in item.value for item in app.success))
                interview_id = Database(path).list_interviews()[0]["id"]
                self.assertEqual(Database(path).get_interview(interview_id)["status"], "completed")
                app.sidebar.radio[0].set_value("Relatórios").run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.get("download_button")), 2)
                next(item for item in app.checkbox if item.label == "Confirmo a exclusão permanente.").check().run()
                click(app, "Excluir entrevista do banco")
                self.assertEqual(Database(path).list_interviews(), [])


if __name__ == "__main__":
    unittest.main()
