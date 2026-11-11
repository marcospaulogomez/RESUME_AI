"""Interface Streamlit; regras da entrevista permanecem no serviço."""

import hashlib
import sqlite3

import streamlit as st

from recruitment.ai import AIUnavailable
from recruitment.audio import validate_wav
from recruitment.channels import Answer
from recruitment.privacy import privacy_notice
from recruitment.reports import KINDS, STATUS, report_json, report_text
from recruitment.service import MAX_ANSWER_CHARS


def clear_candidate_state():
    for key in list(st.session_state):
        if key == "active_interview" or key.startswith(("answer_", "recording_", "review_", "draft_", "delete_candidate_")):
            del st.session_state[key]


def downloads(interview):
    left, right = st.columns(2)
    suffix = interview["id"][:8]
    with left:
        st.download_button("Baixar relatório TXT", report_text(interview).encode("utf-8"),
                           file_name=f"entrevista-{suffix}.txt", mime="text/plain", key=f"txt_{suffix}")
    with right:
        st.download_button("Baixar relatório JSON", report_json(interview).encode("utf-8"),
                           file_name=f"entrevista-{suffix}.json", mime="application/json", key=f"json_{suffix}")


def start_interview(service):
    st.title("Vamos conversar sobre sua trajetória")
    st.write("Uma pergunta por vez, no seu ritmo. Responda por texto ou áudio.")
    jobs = service.db.list_jobs(active_only=True)
    if not jobs:
        st.info("Ainda não há vagas abertas. Cadastre uma vaga no menu lateral para iniciar o teste.")
        return
    job = st.selectbox("Escolha a vaga", jobs, format_func=lambda item: f"#{item['id']} · {item['title']}")
    st.text(job["description"])
    st.caption(f"Um relato inicial, até {job['followup_limit']} complementares e {len(job['questions'])} perguntas padronizadas.")
    st.subheader("Antes de começar")
    st.text(privacy_notice(service.settings))
    with st.form("start_interview"):
        name = st.text_input("Seu nome ou apelido", max_chars=120)
        consent = st.checkbox(
            "Li o aviso e concordo com o tratamento dos dados para esta pré-entrevista, "
            "incluindo o envio à OpenAI quando o modo com IA estiver ativo.", value=False
        )
        if st.form_submit_button("Iniciar entrevista", type="primary"):
            try:
                st.session_state.active_interview = service.start(job["id"], name, consent=consent)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.rerun()


def submit_answer(service, interview, answer):
    try:
        with st.spinner("Registrando sua resposta…"):
            service.submit(interview["id"], answer)
    except (ValueError, AIUnavailable) as exc:
        st.error(str(exc))
        return
    except sqlite3.Error:
        st.error("Não foi possível salvar no banco. Sua resposta permanece no campo; tente novamente.")
        return
    for key in list(st.session_state):
        if key.startswith("draft_"):
            del st.session_state[key]
    st.rerun()


def answer_input(service, interview, turn):
    suffix = f"{interview['id']}_{turn['id']}"
    method = st.radio("Como deseja responder?", ["Texto", "Áudio"], horizontal=True, key=f"method_{suffix}")
    if method == "Texto":
        with st.form(f"text_form_{suffix}"):
            text = st.text_area("Sua resposta", max_chars=MAX_ANSWER_CHARS, height=140, key=f"answer_{suffix}")
            if st.form_submit_button("Enviar resposta", type="primary"):
                submit_answer(service, interview, Answer(turn["id"], text))
        return
    if service.settings.demo_mode:
        st.info("Para testar áudio, configure DEMO_MODE=false e OPENAI_API_KEY no .env e reinicie o app. Você pode continuar por texto.")
        return
    st.caption("Pare a gravação em até 4 minutos. Áudios maiores são recusados antes do envio à API.")
    recording = st.audio_input("Gravar resposta", sample_rate=16000, key=f"recording_{suffix}")
    if recording is None:
        return
    data = recording.getvalue()
    try:
        duration = validate_wav(data)
    except ValueError as exc:
        st.error(str(exc))
        return
    digest = hashlib.sha256(data).hexdigest()
    draft_key = f"draft_{suffix}"
    draft = st.session_state.get(draft_key)
    st.caption(f"Duração: {duration:.1f} segundos. A transcrição usa a API e pode gerar cobrança.")
    if not draft or draft["digest"] != digest:
        if st.button("Transcrever áudio", key=f"transcribe_{suffix}", type="primary"):
            try:
                with st.spinner("Transcrevendo seu áudio…"):
                    transcript = service.ai.transcribe(data)
                if len(transcript) > MAX_ANSWER_CHARS:
                    st.error("A transcrição ficou muito longa. Grave uma resposta mais curta.")
                    return
            except (ValueError, AIUnavailable) as exc:
                st.error(str(exc))
                return
            st.session_state[draft_key] = {"digest": digest, "transcript": transcript, "duration": duration}
            st.rerun()
        return
    st.write("Revise a transcrição antes de enviar. Você pode corrigir o texto abaixo.")
    with st.expander("Transcrição automática original"):
        st.text(draft["transcript"])
    # Uma nova gravação ganha um campo de revisão novo, sem reutilizar a edição anterior.
    with st.form(f"review_form_{suffix}_{digest[:12]}"):
        reviewed = st.text_area("Resposta a confirmar", value=draft["transcript"],
                                max_chars=MAX_ANSWER_CHARS, height=140,
                                key=f"review_{suffix}_{digest[:12]}")
        if st.form_submit_button("Confirmar e enviar resposta", type="primary"):
            submit_answer(service, interview, Answer(
                turn_id=turn["id"], text=reviewed, source="audio",
                transcript=draft["transcript"], audio_seconds=draft["duration"],
            ))


def candidate_page(service):
    interview_id = st.session_state.get("active_interview")
    if not interview_id:
        start_interview(service)
        return
    try:
        interview = service.db.get_interview(interview_id)
    except ValueError as exc:
        clear_candidate_state()
        st.info(str(exc))
        return
    st.title("Sua pré-entrevista")
    st.text(f"{interview['job']['title']} · {interview['candidate_name']}")
    st.caption(f"Código da entrevista: {interview_id}")
    with st.expander("Privacidade e consentimento registrado"):
        st.text(interview["consent_notice"])
    if interview["followup_note"]:
        st.warning(interview["followup_note"])
    answered = sum(turn["answer"] is not None for turn in interview["turns"])
    if answered:
        st.progress(answered / len(interview["turns"]), text=f"{answered} de {len(interview['turns'])} respostas registradas")
    pending = service.pending_turn(interview)
    for turn in interview["turns"]:
        if turn["answer"] is None and turn != pending:
            break
        with st.chat_message("assistant"):
            st.caption(KINDS[turn["kind"]])
            st.text(turn["question"])
        if turn["answer"] is not None:
            with st.chat_message("user"):
                st.text(turn["answer"])
                if turn["source"] == "audio":
                    st.caption(f"Resposta de áudio · {turn['audio_seconds']:.1f}s · transcrição confirmada")
    if interview["status"] == "completed":
        st.success("Entrevista concluída. Suas respostas foram registradas para consulta da equipe.")
        downloads(interview)
        if st.button("Iniciar outra entrevista"):
            clear_candidate_state()
            st.rerun()
    elif interview["mode"] != ("demo" if service.settings.demo_mode else "openai"):
        st.warning("O modo de processamento mudou. Encerre esta sessão e inicie uma nova entrevista para aceitar o aviso atualizado.")
        if st.button("Encerrar sessão"):
            clear_candidate_state()
            st.rerun()
    elif pending:
        answer_input(service, interview, pending)
    with st.expander("Encerrar e excluir meus dados"):
        confirmed = st.checkbox("Quero excluir permanentemente esta entrevista do banco local.",
                                key=f"delete_candidate_{interview_id}")
        if st.button("Excluir meus dados e encerrar", disabled=not confirmed):
            service.db.delete_interview(interview_id)
            clear_candidate_state()
            st.rerun()


def jobs_page(service):
    st.title("Vagas e roteiro")
    st.write("Cadastre de 2 a 4 perguntas relacionadas às atividades da vaga. Elas serão feitas na ordem cadastrada.")
    with st.form("create_job", clear_on_submit=False):
        title = st.text_input("Título da vaga", max_chars=120)
        description = st.text_area("Descrição e experiências relevantes", max_chars=6000)
        questions = st.text_area("Perguntas padronizadas — uma por linha", height=160,
                                 placeholder="Conte sobre um projeto relacionado à vaga.\nComo você organiza as suas atividades?")
        limit = st.selectbox("Máximo de perguntas complementares", [0, 1, 2], index=2)
        st.caption("Use perguntas profissionais e objetivas. Evite pedidos de dados pessoais sensíveis ou critérios discriminatórios.")
        if st.form_submit_button("Cadastrar vaga", type="primary"):
            try:
                service.create_job(title, description, questions.splitlines(), limit)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success("Vaga cadastrada. Ela já está disponível na área de entrevista.")
    jobs = service.db.list_jobs()
    if not jobs and st.button("Criar vaga de exemplo para teste"):
        service.create_job("Assistente administrativo", "Apoio a rotinas administrativas, organização de documentos e atendimento.",
                           ["Conte sobre uma experiência de organização de tarefas ou documentos.",
                            "Como você costuma se comunicar ao trabalhar em equipe?"], 2)
        st.rerun()
    for job in jobs:
        with st.expander(f"#{job['id']} · {job['title']} · {'Aberta' if job['active'] else 'Pausada'}"):
            st.text(job["description"])
            for position, question in enumerate(job["questions"], 1):
                st.text(f"{position}. {question}")
            st.caption(f"Até {job['followup_limit']} perguntas complementares. O roteiro é copiado ao iniciar cada entrevista.")
            if st.button("Pausar vaga" if job["active"] else "Reabrir vaga", key=f"toggle_job_{job['id']}"):
                service.db.set_job_active(job["id"], not job["active"])
                st.rerun()


def reports_page(service):
    st.title("Relatórios")
    st.caption("Registro de perguntas e respostas. Sem avaliação, pontuação ou classificação de candidatos.")
    interviews = service.db.list_interviews()
    if not interviews:
        st.info("As entrevistas aparecerão aqui depois de iniciadas, inclusive as que estiverem em andamento.")
        return
    job_titles = sorted({item["job_title"] for item in interviews})
    selected_job = st.selectbox("Filtrar por vaga", ["Todas as vagas"] + job_titles)
    filtered = [item for item in interviews if selected_job == "Todas as vagas" or item["job_title"] == selected_job]
    selected = st.selectbox("Entrevista", filtered, format_func=lambda item:
                            f"{item['candidate_name']} · {item['job_title']} · {STATUS[item['status']]} · {item['id'][:8]}")
    interview = service.db.get_interview(selected["id"])
    st.text(f"Código: {interview['id']}\nCandidato: {interview['candidate_name']}\nVaga: {interview['job']['title']}")
    st.caption(f"{STATUS[interview['status']]} · {interview['mode']} · Início (UTC): {interview['consent_at']}")
    if interview["followup_note"]:
        st.warning(interview["followup_note"])
    for turn in interview["turns"]:
        st.divider()
        st.caption(f"{turn['position'] + 1} · {KINDS[turn['kind']]}")
        st.text(turn["question"])
        st.text(turn["answer"] if turn["answer"] is not None else "[Resposta pendente]")
        if turn["source"] == "audio":
            st.caption(f"Origem: áudio de {turn['audio_seconds']:.1f}s; a gravação não foi armazenada.")
            with st.expander(f"Transcrição automática original — pergunta {turn['position'] + 1}"):
                st.text(turn["transcript"])
    downloads(interview)
    with st.expander("Aviso aceito pelo candidato"):
        st.text(interview["consent_notice"])
        st.caption(f"Aceite: {interview['consent_at']} · versão {interview['consent_version']}")
    with st.expander("Excluir entrevista"):
        st.caption("Remove o registro local e suas respostas. Arquivos já exportados devem ser tratados separadamente.")
        confirmed = st.checkbox("Confirmo a exclusão permanente.", key=f"delete_report_{interview['id']}")
        if st.button("Excluir entrevista do banco", disabled=not confirmed):
            service.db.delete_interview(interview["id"])
            if st.session_state.get("active_interview") == interview["id"]:
                clear_candidate_state()
            st.rerun()


def render_app(service):
    with st.sidebar:
        st.title("Resume AI")
        st.caption("Pré-entrevista assistida")
        page = st.radio("Navegação", ["Entrevista", "Cadastrar vagas", "Relatórios"])
        st.divider()
        st.caption("MVP local de testes. As áreas de vagas e relatórios não possuem autenticação. Use apenas neste computador.")
    if service.settings.demo_mode:
        st.info("Modo demonstração · sem API · entrevistas por texto · use dados fictícios.")
    else:
        st.caption("IA e transcrição via OpenAI · respostas por texto ou áudio · participação informada")
    try:
        {"Entrevista": candidate_page, "Cadastrar vagas": jobs_page, "Relatórios": reports_page}[page](service)
    except sqlite3.Error:
        st.error("Não foi possível acessar o banco local. Confira a permissão da pasta e tente novamente.")
