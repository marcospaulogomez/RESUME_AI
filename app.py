"""Execute com: python -m streamlit run app.py"""

import sqlite3

import streamlit as st

from recruitment.ai import build_ai
from recruitment.config import load_settings
from recruitment.database import Database
from recruitment.service import InterviewService, utc_now
from recruitment.ui import render_app

st.set_page_config(page_title="Pré-entrevista | Resume AI", page_icon="💬", layout="centered")

try:
    settings = load_settings()
    database = Database(settings.database_path)
    database.initialize()
    database.purge_expired(utc_now())
    service = InterviewService(database, build_ai(settings), settings)
except (ValueError, OSError, sqlite3.Error):
    st.error(
        "Não foi possível iniciar. Confira a configuração do .env, o prazo de retenção, "
        "a chave de API (ou DEMO_MODE=true) e a permissão de acesso ao banco."
    )
    st.stop()

render_app(service)
