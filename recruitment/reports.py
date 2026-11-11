"""Relatório documental determinístico: sem análise, nota ou recomendação."""

import json

KINDS = {"intro": "Relato inicial", "followup": "Complementar", "standard": "Padronizada"}
STATUS = {"in_progress": "Em andamento", "completed": "Concluída"}


def report_data(interview):
    return {
        "report_type": "Registro de pré-entrevista, sem avaliação de candidatos",
        "interview_id": interview["id"],
        "candidate": interview["candidate_name"],
        "job": interview["job"],
        "status": interview["status"],
        "started_at": interview["consent_at"],
        "completed_at": interview["completed_at"],
        "expires_at": interview["expires_at"],
        "mode": interview["mode"],
        "models": {"text": interview["text_model"], "transcription": interview["transcription_model"]},
        "followup_note": interview["followup_note"],
        "consent": {"version": interview["consent_version"], "accepted_at": interview["consent_at"],
                    "notice": interview["consent_notice"]},
        "questions_and_answers": [{
            "position": turn["position"] + 1,
            "kind": turn["kind"],
            "question": turn["question"],
            "answer": turn["answer"],
            "source": turn["source"],
            "automatic_transcript": turn["transcript"],
            "audio_seconds": turn["audio_seconds"],
            "answered_at": turn["answered_at"],
        } for turn in interview["turns"]],
    }


def report_json(interview):
    return json.dumps(report_data(interview), ensure_ascii=False, indent=2)


def report_text(interview):
    lines = [
        "REGISTRO DE PRÉ-ENTREVISTA — SEM AVALIAÇÃO",
        f"Código: {interview['id']}",
        f"Candidato: {interview['candidate_name']}",
        f"Vaga: {interview['job']['title']}",
        f"Descrição da vaga: {interview['job']['description']}",
        f"Situação: {STATUS[interview['status']]}",
        f"Modo: {interview['mode']}",
        f"Início (UTC): {interview['consent_at']}",
        f"Conclusão (UTC): {interview['completed_at'] or 'Ainda não concluída'}",
        f"Retenção local até (UTC): {interview['expires_at']}",
        "Este relatório reproduz os registros, sem pontuação, classificação ou parecer.",
    ]
    if interview["followup_note"]:
        lines.extend(["", interview["followup_note"]])
    for turn in interview["turns"]:
        lines.extend(["", f"{turn['position'] + 1}. {KINDS[turn['kind']]}",
                      f"Pergunta: {turn['question']}",
                      f"Resposta confirmada: {turn['answer'] if turn['answer'] is not None else '[Pendente]'}"])
        if turn["source"] == "audio":
            lines.extend([f"Áudio: {turn['audio_seconds']:.1f} segundos (gravação não armazenada)",
                          f"Transcrição automática original: {turn['transcript']}"])
        elif turn["source"] == "text":
            lines.append("Origem: texto")
    lines.extend(["", f"ACEITE — versão {interview['consent_version']}",
                  f"Registrado em (UTC): {interview['consent_at']}", interview["consent_notice"]])
    return "\n".join(lines)
