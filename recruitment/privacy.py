"""Aviso versionado e guardado junto ao aceite da entrevista."""

from recruitment.config import Settings

NOTICE_VERSION = "1.0"


def privacy_notice(settings: Settings) -> str:
    processing = (
        "Neste teste em modo demonstração, as respostas ficam no computador local; "
        "não há envio à API e áudio não está disponível."
        if settings.demo_mode else
        "O relato inicial e a descrição da vaga são enviados à OpenAI para formular "
        "até duas perguntas complementares. Se você optar por áudio, a gravação "
        "também será enviada à OpenAI para transcrição. Esse processamento pode "
        "ocorrer fora do Brasil, conforme os termos e controles do provedor. "
        "O aplicativo não envia seu nome separadamente à API; informações que "
        "você mencionar no relato ou no áudio também serão transmitidas."
    )
    return (
        f"Aviso de privacidade e uso de IA — versão {NOTICE_VERSION}\n\n"
        f"Responsável pelo tratamento: {settings.controller}. "
        f"Contato de privacidade: {settings.privacy_contact}.\n\n"
        "Finalidade: registrar sua trajetória e suas respostas para consulta da "
        "equipe de recrutamento nesta pré-entrevista. A IA auxilia na coleta e na "
        "transcrição; não avalia, pontua, classifica ou elimina candidatos. "
        "As perguntas padronizadas são cadastradas pela equipe da vaga.\n\n"
        "Dados coletados: nome ou apelido, vaga, perguntas, respostas, transcrições, "
        "duração dos áudios e registro deste aceite. Não informe documentos, dados "
        "de saúde, religião ou outras informações sensíveis desnecessárias.\n\n"
        f"{processing}\n\n"
        "Você pode responder por texto em qualquer etapa e revisar a transcrição "
        "antes de enviá-la. São mantidos o texto transcrito automaticamente e a "
        "versão que você confirmar. A gravação não é salva no banco; é usada "
        "temporariamente na sessão e enviada ao provedor quando houver transcrição.\n\n"
        f"Os registros locais ficam disponíveis à equipe por até {settings.retention_days} "
        "dias a partir do início, com limpeza no próximo uso do aplicativo após "
        "esse prazo. Cópias exportadas e o tratamento realizado pelo provedor "
        "seguem os controles dos respectivos responsáveis.\n\n"
        "A participação é voluntária. Você pode encerrar e excluir os dados desta "
        "entrevista pela interface enquanto a sessão estiver aberta. Para solicitar "
        "acesso, correção, exclusão ou revogação do consentimento posteriormente, "
        "contate o responsável e informe o código da entrevista. Se preferir outro "
        "meio de participação, procure esse mesmo contato antes de iniciar."
    )
