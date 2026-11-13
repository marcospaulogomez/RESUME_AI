# Resume AI — pré-entrevistas

MVP em Python, Streamlit e SQLite. O candidato conversa por texto ou grava áudio;
a IA auxilia a coleta de informações. **Não há avaliação, pontuação, ranking,
classificação, recomendação de contratação ou eliminação de candidatos.**

## Instalação no Windows / VS Code

Use Python 3.11 ou superior, com pip. Abra esta pasta no VS Code e execute no
terminal PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Abra **http://127.0.0.1:8501**. Não é necessário ativar o ambiente virtual.
Se `python` abrir a Microsoft Store, selecione uma instalação real do Python
ou use `py -3 -m venv .venv`. No VS Code, execute **Python: Select Interpreter**
e selecione `.venv\Scripts\python.exe`; a configuração de depuração também
está disponível com F5 (extensões Python e Python Debugger).

Linux/macOS: crie o ambiente com `python3 -m venv .venv`, copie o exemplo com
`cp .env.example .env` e substitua `.\.venv\Scripts\python.exe` por
`.venv/bin/python` nos comandos. Selecione esse interpretador no VS Code.

## Primeiro teste, sem custos de API

O padrão é `DEMO_MODE=true`. Não precisa de chave nem de `.env` para abrir o app.

1. Acesse **Cadastrar vagas** e crie uma vaga, com duas a quatro perguntas, ou
   clique em **Criar vaga de exemplo para teste**.
2. Em **Entrevista**, selecione a vaga, leia o aviso, informe um nome fictício
   e marque o aceite.
3. Envie o relato inicial. O modo demonstração usa um trecho desse relato para
   formular uma complementar fixa, respeitando o limite cadastrado. Isso é
   uma simulação, sem modelo de IA ou transcrição.
4. Responda às perguntas padronizadas. O relatório é disponibilizado ao finalizar.
5. Consulte **Relatórios** e exporte TXT ou JSON. Entrevistas em andamento também
   aparecem, com respostas pendentes identificadas.

O cadastro aceita de zero a duas complementares. Pausar uma vaga impede novos
inícios e preserva as entrevistas já iniciadas. O roteiro da vaga é copiado para
cada entrevista; alterações futuras na vaga não modificam o histórico.

## Ativar IA e áudio

Edite `.env`:

```dotenv
DEMO_MODE=false
OPENAI_API_KEY=sua-chave
OPENAI_TEXT_MODEL=gpt-4.1-mini
OPENAI_TRANSCRIPTION_MODEL=gpt-transcribe
DATA_CONTROLLER=Nome da organização responsável
PRIVACY_CONTACT=privacidade@sua-organizacao.com
DATA_RETENTION_DAYS=30
DATABASE_PATH=data/interviews.db
```

Reinicie o Streamlit após alterar `.env`. Use uma chave da API OpenAI com crédito
e acesso aos modelos configurados; não a insira na interface nem no repositório.
Uma entrevista iniciada em demonstração não pode continuar em modo real sem um
novo aceite; encerre a sessão e inicie outra.

Na conversa, selecione **Áudio**, autorize o microfone, grave e pare em até quatro
minutos. Clique em **Transcrever áudio**, revise ou corrija o resultado e escolha
**Confirmar e enviar resposta**. A transcrição original e o texto confirmado
aparecem no relatório. É possível alternar para texto em qualquer etapa.
As perguntas do assistente são apresentadas em texto; não há síntese de voz.

O navegador grava WAV mono a 16 kHz. O servidor valida formato, integridade,
tamanho máximo de 10 MB e duração máxima de 240 segundos **antes da API**.
O widget não interrompe a gravação automaticamente: gravações mais longas são
recusadas, sem truncamento. Microfone requer permissão do navegador; em geral,
`localhost`/`127.0.0.1` são contextos permitidos. Não há upload de MP3/OGG neste MVP,
o que dispensa FFmpeg. Os quatro minutos se aplicam a todas as respostas de áudio.

### Fluxo e custo

- Um relato inicial → zero a duas complementares → duas a quatro padronizadas.
- Uma chamada de texto após o relato inicial, somente se o limite for maior que
  zero. As complementares são planejadas de uma vez. O modelo recebe a vaga, o
  relato e as perguntas cadastradas; não recebe o nome em um campo separado.
- A IA seleciona trechos literais e um foco permitido; o código usa moldes neutros
  para formular as complementares. Trechos inventados e focos não previstos são
  descartados. Não se exibe texto analítico livre gerado pelo modelo.
- Uma chamada de transcrição por gravação solicitada. A transcrição fica na sessão
  para revisão; não é refeita ao enviar a resposta. Uma nova tentativa explícita
  após falha pode gerar nova cobrança. O SDK permite uma repetição de requisição
  em falhas transitórias; não há garantia de cobrança única nessas situações.
- As perguntas padronizadas e o relatório não usam IA. Não há TTS, embeddings,
  banco vetorial ou framework de agentes.
- Se a geração de complementares falhar, o relato é salvo e o fluxo segue com as
  padronizadas. A ocorrência fica visível na conversa e no relatório. Se a
  transcrição falhar, é possível tentar novamente ou responder por texto.

Os modelos são configuráveis; confira disponibilidade e preços na sua conta.
Os padrões usam a [Responses API com saída estruturada](https://developers.openai.com/api/docs/guides/structured-outputs),
o modelo [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
e o modelo indicado na [documentação oficial de transcrição](https://developers.openai.com/api/docs/guides/speech-to-text).
Não existe custo fixo garantido por entrevista; depende do uso e dos modelos.

## Dados e aviso ao candidato

O aviso identifica o responsável e o contato, explica finalidade, dados, envio à
OpenAI, possível processamento internacional, prazo de retenção e direitos.
O aceite não vem marcado e é obrigatório antes de criar uma entrevista.
O banco mantém uma cópia do aviso, versão e instante do aceite em UTC.

Os áudios não são salvos no SQLite nem em arquivos pela aplicação. Permanecem
temporariamente na sessão do navegador/Streamlit e são enviados à OpenAI quando
o candidato solicita transcrição. O banco armazena perguntas, respostas, textos
transcritos, duração, identificação informada e metadados do fluxo. Os rascunhos
não são persistidos no banco; sua liberação da memória após o encerramento da
sessão depende do ciclo do Streamlit.

`data/interviews.db` é criado automaticamente e ignorado pelo Git, assim como
`.env`. O aplicativo usa `store=False` nas chamadas de texto, mas isso não significa
ausência de retenção do provedor. Consulte os [controles de dados da OpenAI](https://developers.openai.com/api/docs/guides/your-data).

Cada entrevista tem um prazo de expiração definido no início. Registros vencidos
são apagados no próximo carregamento/interação do aplicativo; com o app desligado,
a limpeza aguarda a próxima execução. Alterar a configuração não altera prazos
de entrevistas existentes. O candidato pode excluir sua entrevista durante a
sessão; o operador também pode excluí-la em **Relatórios**, com remoção em cascata
das respostas. Os arquivos exportados e eventuais backups ficam sob controle do
responsável. O código da entrevista facilita solicitações posteriores.

Este protótipo implementa aviso e registro de consentimento para testes, mas não
constitui certificação de conformidade com a LGPD. Antes de uso real, o responsável
deve definir a base legal apropriada, o atendimento dos direitos, o mecanismo de
transferência internacional e as medidas de segurança e retenção, considerando a
[Lei nº 13.709/2018](https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-normaatualizada-pl.html).

## Organização

```text
app.py                  Inicialização
recruitment/
  config.py             Configuração via .env
  database.py           SQLite e exclusões
  privacy.py            Aviso versionado
  audio.py              Validação WAV
  ai.py                 Protocolo de IA, OpenAI e demonstração
  channels.py           Contrato de respostas independente de canal
  service.py            Fluxo e regras da entrevista
  reports.py            Exportações documentais TXT/JSON
  ui.py                 Telas Streamlit
tests/                  Testes com banco temporário e API simulada
.streamlit/config.toml   Interface local e telemetria desativada
.vscode/                Interpretador e depuração
```

## Futura integração com WhatsApp Business

Não há integração WhatsApp, webhooks ou chamadas à Meta nesta versão. O serviço
não importa Streamlit. Um adaptador futuro poderá usar `InterviewService.start`,
`pending_turn` e `submit`, traduzindo mensagens para o contrato `Answer` e
encaminhando as perguntas retornadas ao canal. O `turn_id` identifica a pergunta
esperada e impede gravar a mesma resposta duas vezes.

O adaptador deverá implementar, usando a **API oficial do WhatsApp Business**:
verificação/assinatura de webhook, autenticação e associação do remetente a uma
entrevista, idempotência por ID de mensagem da Meta, conversão de OGG/Opus para WAV
com validação de duração, consentimento compatível com o canal, envio de perguntas
e tratamento das regras de janela de conversa/templates. A associação entre número
e entrevista deverá ficar em armazenamento protegido; um UUID sozinho não é
autenticação. Nenhuma dessas capacidades é simulada como se já estivesse pronta.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes usam banco temporário e dados fictícios; não acessam APIs pagas. Cobrem
ordem/limites, consentimento, persistência, relatórios, revisão de transcrição,
duplicidade, expiração, exclusão, falhas de API e navegação pelo Streamlit.
A chamada real e a captura do microfone devem ser verificadas com sua chave e
seu navegador.

## Limites desta versão local

- As áreas de operador e candidato compartilham o app, sem login ou isolamento de
  usuários. O servidor escuta somente em `127.0.0.1`. Use dados fictícios e não
  publique nem compartilhe esta instalação com candidatos reais.
- Não há criptografia do SQLite, autenticação, gestão de permissões, trilha de
  auditoria completa ou recuperação de sessão do candidato após fechar o navegador.
  Os registros permanecem acessíveis ao operador até expiração ou exclusão.
- Não há edição de respostas já enviadas pela interface; correções posteriores
  devem ser solicitadas ao responsável pelo tratamento.
- As perguntas cadastradas exigem revisão humana quanto à pertinência e à
  privacidade. O aplicativo não julga candidatos nem valida critérios da vaga.
