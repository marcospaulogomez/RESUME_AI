"""SQLite: conexões curtas, parâmetros SQL e exclusão em cascata."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA secure_delete = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    questions_json TEXT NOT NULL,
                    followup_limit INTEGER NOT NULL CHECK(followup_limit BETWEEN 0 AND 2),
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS interviews (
                    id TEXT PRIMARY KEY,
                    job_id INTEGER NOT NULL REFERENCES jobs(id),
                    candidate_name TEXT NOT NULL,
                    job_snapshot TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    text_model TEXT NOT NULL,
                    transcription_model TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'in_progress'
                        CHECK(status IN ('in_progress', 'completed')),
                    followup_note TEXT NOT NULL DEFAULT '',
                    consent_version TEXT NOT NULL,
                    consent_notice TEXT NOT NULL,
                    consent_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('intro', 'followup', 'standard')),
                    question TEXT NOT NULL,
                    answer TEXT,
                    source TEXT CHECK(source IN ('text', 'audio')),
                    transcript TEXT,
                    audio_seconds REAL,
                    answered_at TEXT,
                    UNIQUE(interview_id, position)
                );
                CREATE INDEX IF NOT EXISTS idx_turns_interview ON turns(interview_id);
                CREATE INDEX IF NOT EXISTS idx_interviews_expiration ON interviews(expires_at);
            """)

    def list_jobs(self, active_only=False):
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs " + ("WHERE active = 1 " if active_only else "")
                + "ORDER BY id DESC"
            ).fetchall()
        return [self._job(row) for row in rows]

    @staticmethod
    def _job(row):
        if row is None:
            raise ValueError("Vaga não encontrada.")
        result = dict(row)
        result["questions"] = json.loads(result.pop("questions_json"))
        return result

    def get_job(self, job_id):
        with self.connection() as conn:
            return self._job(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())

    def set_job_active(self, job_id, active):
        with self.connection() as conn:
            conn.execute("UPDATE jobs SET active = ? WHERE id = ?", (int(active), job_id))

    def get_interview(self, interview_id):
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM interviews WHERE id = ?", (interview_id,)).fetchone()
            if row is None:
                raise ValueError("Entrevista não encontrada ou já excluída pelo prazo de retenção.")
            interview = dict(row)
            interview["job"] = json.loads(interview.pop("job_snapshot"))
            interview["turns"] = [dict(turn) for turn in conn.execute(
                "SELECT * FROM turns WHERE interview_id = ? ORDER BY position", (interview_id,)
            ).fetchall()]
        return interview

    def list_interviews(self):
        with self.connection() as conn:
            return [dict(row) for row in conn.execute("""
                SELECT i.id, i.candidate_name, i.status, i.consent_at, i.expires_at,
                       json_extract(i.job_snapshot, '$.title') AS job_title
                FROM interviews i ORDER BY i.consent_at DESC
            """).fetchall()]

    def delete_interview(self, interview_id):
        with self.connection() as conn:
            conn.execute("DELETE FROM interviews WHERE id = ?", (interview_id,))

    def purge_expired(self, now):
        with self.connection() as conn:
            return conn.execute("DELETE FROM interviews WHERE expires_at <= ?", (now,)).rowcount
