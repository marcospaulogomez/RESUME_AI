"""Regras e fluxo da entrevista; sem dependência do Streamlit ou WhatsApp."""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from recruitment.ai import AIUnavailable, InterviewAI
from recruitment.audio import MAX_AUDIO_SECONDS
from recruitment.channels import Answer
from recruitment.config import Settings
from recruitment.database import Database
from recruitment.privacy import NOTICE_VERSION, privacy_notice

INTRO_QUESTION = (
    "Para começar, conte um resumo da sua trajetória acadêmica e profissional, "
    "destacando experiências relacionadas a esta vaga. Você pode escrever ou "
    "enviar um áudio de até 4 minutos."
)
MAX_ANSWER_CHARS = 12000


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class InterviewService:
    def __init__(self, database: Database, ai: InterviewAI, settings: Settings):
        self.db, self.ai, self.settings = database, ai, settings

    def create_job(self, title, description, questions, followup_limit=2):
        title, description = title.strip(), description.strip()
        questions = [q.strip() for q in questions if q.strip()]
        if not title or len(title) > 120 or not description or len(description) > 6000:
            raise ValueError("Preencha título (até 120 caracteres) e descrição (até 6.000).")
        if not 2 <= len(questions) <= 4 or any(len(q) > 600 for q in questions):
            raise ValueError("Cadastre de 2 a 4 perguntas, com até 600 caracteres cada.")
        if len({q.casefold() for q in questions}) != len(questions):
            raise ValueError("As perguntas padronizadas devem ser diferentes entre si.")
        if followup_limit not in {0, 1, 2}:
            raise ValueError("O limite de perguntas complementares deve ser de 0 a 2.")
        with self.db.connection() as conn:
            return conn.execute("""
                INSERT INTO jobs(title, description, questions_json, followup_limit, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (title, description, json.dumps(questions, ensure_ascii=False),
                  followup_limit, utc_now())).lastrowid

    def start(self, job_id, candidate_name, consent=False):
        if not consent:
            raise ValueError("É necessário ler e aceitar o aviso antes de iniciar.")
        name = candidate_name.strip()
        if not name or len(name) > 120:
            raise ValueError("Informe seu nome ou apelido, com até 120 caracteres.")
        job = self.db.get_job(job_id)
        if not job["active"]:
            raise ValueError("Esta vaga não está recebendo novas entrevistas.")
        interview_id = str(uuid4())
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=self.settings.retention_days)
        with self.db.connection() as conn:
            conn.execute("""
                INSERT INTO interviews(
                    id, job_id, candidate_name, job_snapshot, mode, text_model,
                    transcription_model, consent_version, consent_notice, consent_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (interview_id, job_id, name, json.dumps(job, ensure_ascii=False),
                  "demo" if self.settings.demo_mode else "openai",
                  self.settings.text_model, self.settings.transcription_model,
                  NOTICE_VERSION, privacy_notice(self.settings),
                  now.isoformat(timespec="seconds"), expires.isoformat(timespec="seconds")))
            conn.execute("""
                INSERT INTO turns(interview_id, position, kind, question) VALUES (?, 0, 'intro', ?)
            """, (interview_id, INTRO_QUESTION))
        return interview_id

    @staticmethod
    def pending_turn(interview):
        return next((turn for turn in interview["turns"] if turn["answer"] is None), None)

    def submit(self, interview_id, answer: Answer):
        interview = self.db.get_interview(interview_id)
        if interview["expires_at"] <= utc_now():
            self.db.delete_interview(interview_id)
            raise ValueError("O prazo de retenção desta entrevista terminou.")
        if interview["status"] != "in_progress":
            raise ValueError("Esta entrevista já foi finalizada.")
        expected_mode = "demo" if self.settings.demo_mode else "openai"
        if interview["mode"] != expected_mode:
            raise ValueError("O modo de IA mudou. Inicie outra entrevista para registrar um novo aceite.")
        pending = self.pending_turn(interview)
        if pending is None or pending["id"] != answer.turn_id:
            raise ValueError("Essa pergunta já foi respondida ou não é a pergunta atual.")
        text = answer.text.strip()
        if not text or len(text) > MAX_ANSWER_CHARS:
            raise ValueError("A resposta deve conter de 1 a 12.000 caracteres.")
        if answer.source not in {"text", "audio"}:
            raise ValueError("Origem da resposta inválida.")
        if answer.source == "audio":
            if (not answer.transcript or not answer.transcript.strip()
                    or len(answer.transcript) > MAX_ANSWER_CHARS
                    or answer.audio_seconds is None
                    or not 0 < answer.audio_seconds <= MAX_AUDIO_SECONDS):
                raise ValueError("A resposta de áudio exige transcrição e duração válida até 4 minutos.")
        elif answer.transcript is not None or answer.audio_seconds is not None:
            raise ValueError("Uma resposta por texto não deve conter metadados de áudio.")

        followups, note = [], ""
        if pending["kind"] == "intro":
            try:
                followups = self.ai.followups(interview["job"], text, interview["job"]["followup_limit"])
                # A ordem e o limite são regras do serviço, não decisões da IA.
                followups = list(followups)[:interview["job"]["followup_limit"]]
            except AIUnavailable:
                note = (
                    "A geração das perguntas complementares ficou indisponível. "
                    "A entrevista seguiu com as perguntas padronizadas cadastradas."
                )

        with self.db.connection() as conn:
            updated = conn.execute("""
                UPDATE turns SET answer = ?, source = ?, transcript = ?, audio_seconds = ?, answered_at = ?
                WHERE id = ? AND interview_id = ? AND answer IS NULL
            """, (text, answer.source, answer.transcript, answer.audio_seconds,
                  utc_now(), answer.turn_id, interview_id)).rowcount
            if not updated:
                raise ValueError("Essa resposta já foi registrada. Atualize a conversa.")
            if pending["kind"] == "intro":
                planned = [("followup", question) for question in followups]
                planned.extend(("standard", question) for question in interview["job"]["questions"])
                conn.executemany("""
                    INSERT INTO turns(interview_id, position, kind, question) VALUES (?, ?, ?, ?)
                """, [(interview_id, position, kind, question)
                      for position, (kind, question) in enumerate(planned, start=1)])
                conn.execute("UPDATE interviews SET followup_note = ? WHERE id = ?", (note, interview_id))
            remaining = conn.execute(
                "SELECT COUNT(*) FROM turns WHERE interview_id = ? AND answer IS NULL", (interview_id,)
            ).fetchone()[0]
            if remaining == 0:
                conn.execute("UPDATE interviews SET status = 'completed', completed_at = ? WHERE id = ?",
                             (utc_now(), interview_id))
        return self.db.get_interview(interview_id)
