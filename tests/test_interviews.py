import io
import json
import tempfile
import unittest
import wave
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from recruitment.ai import AIUnavailable, DemoInterviewAI, OpenAIInterviewAI, render_followups
from recruitment.audio import validate_wav
from recruitment.channels import Answer
from recruitment.config import Settings
from recruitment.database import Database
from recruitment.reports import report_data, report_json, report_text
from recruitment.service import InterviewService, utc_now


def wav_bytes(seconds=1):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * (16000 * seconds))
    return stream.getvalue()


class InterviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = Settings(Path(self.temp.name) / "test.db", True, "", "text-model",
                                 "audio-model", 30, "Empresa de teste", "contato@example.com")
        self.db = Database(self.settings.database_path)
        self.db.initialize()
        self.ai = Mock()
        self.ai.followups.return_value = ["Qual foi sua participação?", "Quais atividades realizou?"]
        self.service = InterviewService(self.db, self.ai, self.settings)
        self.questions = ["Conte sobre um projeto.", "Como você organiza tarefas?"]
        self.job_id = self.service.create_job("Assistente", "Rotinas administrativas", self.questions, 2)

    def start(self):
        return self.service.start(self.job_id, "Candidata fictícia", consent=True)

    def answer_next(self, interview_id, text="Minha resposta.", **kwargs):
        interview = self.db.get_interview(interview_id)
        turn = self.service.pending_turn(interview)
        return self.service.submit(interview_id, Answer(turn["id"], text, **kwargs))

    def test_consent_is_required_before_storing_candidate(self):
        with self.assertRaises(ValueError):
            self.service.start(self.job_id, "Teste", consent=False)
        self.assertEqual(self.db.list_interviews(), [])

    def test_complete_flow_order_limit_and_persistence(self):
        self.ai.followups.return_value += ["Terceira pergunta proibida pelo limite"]
        interview_id = self.start()
        interview = self.answer_next(interview_id, "Trabalhei em um projeto de organização de documentos.")
        self.assertEqual([turn["kind"] for turn in interview["turns"]],
                         ["intro", "followup", "followup", "standard", "standard"])
        self.assertEqual([turn["question"] for turn in interview["turns"][-2:]], self.questions)
        while self.service.pending_turn(interview):
            interview = self.answer_next(interview_id)
        reloaded = Database(self.settings.database_path).get_interview(interview_id)
        self.assertEqual(reloaded["status"], "completed")
        self.assertIsNotNone(reloaded["completed_at"])
        self.ai.followups.assert_called_once()
        self.assertTrue(all(turn["answer"] for turn in reloaded["turns"]))

    def test_zero_complementary_and_four_standard_questions(self):
        self.ai.followups.return_value = []
        questions = self.questions + ["Como registra uma entrega?", "Que ferramentas já utilizou?"]
        job_id = self.service.create_job("Outra vaga", "Descrição", questions, 0)
        interview_id = self.service.start(job_id, "Teste", consent=True)
        interview = self.answer_next(interview_id)
        self.assertEqual([turn["kind"] for turn in interview["turns"]], ["intro"] + ["standard"] * 4)

    def test_standard_questions_must_be_two_to_four_and_unique(self):
        for questions in [["Uma pergunta"], [str(i) for i in range(5)], ["Igual", "igual"]]:
            with self.subTest(questions=questions), self.assertRaises(ValueError):
                self.service.create_job("Vaga", "Descrição", questions)

    def test_duplicate_and_out_of_order_responses_are_rejected(self):
        interview_id = self.start()
        first_turn = self.db.get_interview(interview_id)["turns"][0]["id"]
        self.answer_next(interview_id)
        with self.assertRaises(ValueError):
            self.service.submit(interview_id, Answer(first_turn, "Duplicada"))
        last_turn = self.db.get_interview(interview_id)["turns"][-1]["id"]
        with self.assertRaises(ValueError):
            self.service.submit(interview_id, Answer(last_turn, "Fora de ordem"))
        self.assertEqual(sum(t["answer"] is not None for t in self.db.get_interview(interview_id)["turns"]), 1)

    def test_api_outage_preserves_answer_and_follows_standard_script(self):
        self.ai.followups.side_effect = AIUnavailable("Sem API")
        interview_id = self.start()
        interview = self.answer_next(interview_id, "Meu relato")
        self.assertEqual(interview["turns"][0]["answer"], "Meu relato")
        self.assertEqual(len(interview["turns"]), 3)
        self.assertIn("indisponível", interview["followup_note"])

    def test_audio_report_preserves_original_and_confirmed_transcript(self):
        interview_id = self.start()
        interview = self.answer_next(interview_id, "Versão corrigida", source="audio",
                                     transcript="Versão automática", audio_seconds=14.2)
        data = report_data(interview)
        first = data["questions_and_answers"][0]
        self.assertEqual(first["answer"], "Versão corrigida")
        self.assertEqual(first["automatic_transcript"], "Versão automática")
        self.assertEqual(first["audio_seconds"], 14.2)
        self.assertEqual(json.loads(report_json(interview)), data)
        self.assertIn("Versão automática", report_text(interview))
        self.assertIn("Versão corrigida", report_text(interview))
        self.assertIn("notice", data["consent"])
        for field in ("score", "ranking", "classification", "recommendation"):
            self.assertNotIn(field, data)

    def test_deletion_cascades_to_all_responses(self):
        interview_id = self.start()
        self.answer_next(interview_id)
        self.db.delete_interview(interview_id)
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0], 0)
        self.assertEqual(self.db.list_interviews(), [])

    def test_retention_removes_expired_interview_only(self):
        expired, retained = self.start(), self.start()
        with self.db.connection() as conn:
            conn.execute("UPDATE interviews SET expires_at = ? WHERE id = ?", ("2000-01-01T00:00:00+00:00", expired))
        self.assertEqual(self.db.purge_expired(utc_now()), 1)
        self.assertEqual([item["id"] for item in self.db.list_interviews()], [retained])
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM turns WHERE interview_id = ?", (expired,)).fetchone()[0], 0)

    def test_job_snapshot_does_not_change_existing_interview(self):
        interview_id = self.start()
        with self.db.connection() as conn:
            conn.execute("UPDATE jobs SET questions_json = ?, title = ? WHERE id = ?",
                         ('["Mudou", "Outra"]', "Título alterado", self.job_id))
        interview = self.answer_next(interview_id)
        self.assertEqual(interview["job"]["title"], "Assistente")
        self.assertEqual([t["question"] for t in interview["turns"][-2:]], self.questions)

    def test_paused_job_disallows_new_interviews(self):
        self.db.set_job_active(self.job_id, False)
        with self.assertRaises(ValueError):
            self.start()

    def test_invalid_audio_metadata_is_rejected_without_saving(self):
        interview_id = self.start()
        with self.assertRaises(ValueError):
            self.answer_next(interview_id, source="audio", transcript="Texto", audio_seconds=241)
        self.assertIsNone(self.db.get_interview(interview_id)["turns"][0]["answer"])

    def test_mode_change_requires_new_consent(self):
        interview_id = self.start()
        other_service = InterviewService(self.db, self.ai, replace(self.settings, demo_mode=False))
        turn_id = self.db.get_interview(interview_id)["turns"][0]["id"]
        with self.assertRaises(ValueError):
            other_service.submit(interview_id, Answer(turn_id, "Meu relato"))


class AudioAndAITests(unittest.TestCase):
    def test_wav_duration_boundary_and_invalid_input(self):
        self.assertEqual(validate_wav(wav_bytes(240)), 240)
        for data in (wav_bytes(241), b"not a wav", wav_bytes(1)[:-100], b""):
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                validate_wav(data)

    def test_generated_content_cannot_invent_experiences_or_return_evaluations(self):
        story = "Trabalhei na organização de documentos e relatórios."
        payload = {"topics": [
            {"excerpt": "Experiência que não existe", "focus": "participation"},
            {"excerpt": "organização de documentos", "focus": "score"},
            {"excerpt": "organização de documentos", "focus": "participation"},
            {"excerpt": "organização de documentos", "focus": "results"},
            {"excerpt": "documentos e relatórios", "focus": "actions"},
        ]}
        questions = render_followups(payload, story, 2)
        self.assertEqual(len(questions), 2)
        self.assertIn("Qual foi sua participação", questions[0])
        self.assertEqual(render_followups(payload, story, 0), [])
        self.assertEqual(render_followups({"topics": None}, story, 2), [])

    def test_real_api_adapter_uses_structured_output_and_no_response_storage(self):
        settings = Settings(Path("unused.db"), False, "fake-test-key", "test-text", "test-audio",
                            30, "Teste", "contato@example.com")
        with patch("recruitment.ai.OpenAI") as client_factory:
            client = client_factory.return_value
            client.responses.create.return_value = SimpleNamespace(
                status="completed", output_text=json.dumps({"topics": [
                    {"excerpt": "organização de documentos", "focus": "actions"},
                ]})
            )
            adapter = OpenAIInterviewAI(settings)
            questions = adapter.followups({"title": "Vaga", "description": "Rotinas", "questions": ["Um?", "Dois?"]},
                                          "Trabalhei na organização de documentos.", 2)
            self.assertEqual(len(questions), 1)
            request = client.responses.create.call_args.kwargs
            self.assertFalse(request["store"])
            self.assertTrue(request["text"]["format"]["strict"])
            self.assertEqual(request["model"], "test-text")
            client.audio.transcriptions.create.return_value = SimpleNamespace(text="Transcrição de teste")
            self.assertEqual(adapter.transcribe(wav_bytes()), "Transcrição de teste")
            self.assertEqual(client.audio.transcriptions.create.call_args.kwargs["model"], "test-audio")
            client.audio.transcriptions.create.reset_mock()
            with self.assertRaises(ValueError):
                adapter.transcribe(wav_bytes(241))
            client.audio.transcriptions.create.assert_not_called()

    def test_demo_has_no_audio_or_network(self):
        demo = DemoInterviewAI()
        self.assertEqual(len(demo.followups({}, "Uma experiência profissional de teste", 2)), 1)
        with self.assertRaises(AIUnavailable):
            demo.transcribe(wav_bytes())


if __name__ == "__main__":
    unittest.main()
