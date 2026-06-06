# Assistente pessoal no Telegram

## Objetivo

Criar um bot no Telegram para organizar compromissos, agenda, lembretes, estudos, devocionais e resumos em audio. O assistente deve aprender preferencias do usuario ao longo das conversas e usar essas informacoes para sugerir uma rotina melhor.

## Canais de entrada e saida

- Telegram por texto.
- Telegram por audio.
- Resposta em texto quando fizer sentido.
- Resposta em audio quando o usuario enviar audio ou quando a rotina pedir resumo falado.

## Integracoes desejadas

- OpenAI API para conversar, interpretar mensagens, transcrever audio e gerar respostas.
- Telegram Bot API para receber e responder mensagens.
- Google Calendar para criar, editar e consultar eventos.
- Gmail para resumir emails importantes, detectar compromissos e sugerir lembretes.
- Telefone, se possivel, via uma das opcoes:
  - notificacoes pelo proprio Telegram;
  - Google Calendar no celular;
  - WhatsApp/SMS por servicos externos, caso seja realmente necessario;
  - app proprio no futuro, se o projeto crescer.

## Importante sobre chaves e tokens

O usuario precisa criar e fornecer as proprias chaves:

- Token do bot no Telegram, criado no BotFather.
- Chave da OpenAI API.
- Credenciais OAuth do Google para Calendar e Gmail.

Nao e recomendado colocar chaves em codigo. Elas devem ficar em um arquivo `.env` local ou em variaveis de ambiente.

## Rotina principal

## Rotina inicial do usuario

### Dias uteis

- Acorda normalmente entre 5:30 e 6:00.
- Sai para o trabalho entre 7:20 e 7:30.
- Chega ao trabalho por volta de 8:30.
- Tem uma janela livre aproximada no almoco entre 12:00 e 13:30.
- Volta para casa por volta de 17:00.
- Depois das 17:00 nao possui horario fixo, mas quer priorizar estudo e desenvolvimento de projetos.
- Quarta-feira e sexta-feira tem igreja as 19:40.

### Finais de semana

- Acorda por volta de 9:00.
- Domingo tem igreja as 18:00.

### Preferencias espirituais

- Prefere a Biblia Almeida Corrigida.
- Quer receber uma palavra biblica diariamente.

### Estilo esperado do assistente

- Deve ser realmente proativo.
- Deve ajudar a criar estudos e organizar projetos.
- Deve aprender com as conversas ao longo do tempo.
- Deve permitir controle pelo bot, com configuracoes editaveis.
- Deve identificar oportunidades na rotina e sugerir proximas acoes.
- Pode criar eventos automaticamente na agenda.
- O usuario tambem quer conseguir adicionar eventos pelo bot.
- Deve conseguir olhar para os projetos existentes no PC quando essa integracao local estiver configurada.

### Segunda-feira de manha

O assistente inicia a organizacao semanal.

Fluxo sugerido:

1. Pergunta como sera cada dia da semana.
2. Identifica compromissos, estudos, tarefas e horarios livres.
3. Confirma os itens importantes.
4. Cria ou atualiza eventos no Google Calendar.
5. Cria lembretes no proprio sistema.
6. Gera um resumo em audio da semana.

### Todos os dias de manha

Horario padrao em dias uteis: 7:20.

O assistente envia:

- palavra biblica do dia;
- resumo em audio do dia;
- principais compromissos;
- lembretes importantes;
- sugestao breve de foco do dia.

Nos finais de semana, o horario deve ser mais tarde e editavel.

### Atualizacoes durante a semana

O assistente pode atualizar de hora em hora, mas com controle para nao incomodar.

Exemplo:

- Se houver compromisso proximo, avisa.
- Se houver tempo de estudo, envia um resumo em audio do que estudar.
- Se nada importante estiver acontecendo, pode enviar uma atualizacao curta ou ficar quieto, dependendo da configuracao.

## Estudos

Quando o usuario disser que precisa estudar algo:

1. O assistente salva o tema.
2. Pergunta prazo, importancia e duracao desejada, se faltar informacao.
3. Agenda blocos de estudo.
4. No horario de estudar, envia um resumo em audio.
5. Depois do estudo, pergunta se concluiu ou se precisa reagendar.

### Sugestao inicial para estudos e projetos

- Dias uteis sem igreja: bloco principal de 90 minutos apos 18:30.
- Quarta e sexta: estudo leve antes da igreja ou revisao curta depois, se o usuario estiver disposto.
- Almoco: usar apenas para revisoes curtas, leitura, flashcards ou planejamento rapido.
- Sabado: bom dia para blocos maiores de projeto.
- Domingo: rotina mais leve, com preparacao da semana antes da igreja ou depois, se necessario.

O assistente deve evitar lotar a agenda do usuario automaticamente. A postura ideal e sugerir, confirmar e aprender o que funciona.

### Registro de estudos

Quando o usuario mandar um assunto para estudar, o assistente deve:

1. Identificar o tema principal.
2. Classificar o assunto em uma area, por exemplo programacao, trabalho, Biblia, projeto pessoal ou outro.
3. Criar uma anotacao do que precisa estudar.
4. Sugerir um plano de estudo em blocos de 90 minutos.
5. Registrar o que ja foi estudado.
6. Perguntar depois do bloco se o usuario concluiu, entendeu, quer revisar ou quer aprofundar.
7. Manter um historico por assunto, com status:
   - novo;
   - em estudo;
   - revisao;
   - concluido;
   - precisa aprofundar.

Exemplo:

Usuario: "preciso estudar API do Google Calendar"

Assistente:

- identifica o tema como Google Calendar API;
- vincula ao projeto do bot;
- cria um bloco de estudo de 90 minutos;
- no horario certo, envia um resumo em audio;
- depois pergunta o que foi estudado;
- salva o progresso.

## Memoria sobre o usuario

O assistente deve guardar preferencias e fatos uteis, por exemplo:

- horario em que costuma acordar;
- horarios preferidos para estudo;
- temas de estudo recorrentes;
- compromissos fixos;
- estilo preferido de lembrete;
- tom das mensagens;
- versoes editaveis dos horarios de rotina;
- pessoas, lugares e atividades importantes.

Toda memoria deve ser editavel. O usuario pode pedir:

- "mude meu horario de resumo da manha";
- "esqueca essa informacao";
- "me mostre o que voce sabe sobre mim";
- "altere meus finais de semana para 9:30".

## Banco de dados

Sugestao inicial:

- SQLite para comecar simples.
- Tabelas:
  - usuarios;
  - memorias;
  - compromissos;
  - lembretes;
  - blocos_de_estudo;
  - configuracoes;
  - historico_de_conversas;
  - jobs_agendados;

No futuro, pode migrar para PostgreSQL se o sistema crescer.

## Stack tecnica sugerida

- Python.
- python-telegram-bot.
- OpenAI API.
- Google Calendar API.
- Gmail API.
- APScheduler para tarefas agendadas.
- SQLite.
- FastAPI opcional, caso precise de painel web.

## Funcoes principais do bot

- Entender texto livre.
- Transcrever audio.
- Responder por audio.
- Criar lembretes.
- Criar eventos na agenda.
- Consultar agenda do dia e da semana.
- Resumir emails importantes.
- Fazer revisao semanal.
- Enviar devocional diario.
- Enviar resumo diario em audio.
- Enviar resumo de estudo no horario certo.
- Editar configuracoes por conversa.
- Mostrar e editar memoria.

## Comandos sugeridos

- `/inicio` - configurar o assistente.
- `/hoje` - resumo do dia.
- `/semana` - resumo da semana.
- `/agenda` - proximos compromissos.
- `/lembrete` - criar lembrete rapido.
- `/estudo` - cadastrar estudo.
- `/config` - editar horarios e preferencias.
- `/memoria` - ver o que o assistente sabe.
- `/esquecer` - apagar uma memoria.

## Configuracoes editaveis

- Horario do resumo da manha em dias uteis.
- Horario do resumo da manha em finais de semana.
- Frequencia das atualizacoes durante o dia.
- Se quer audio sempre, nunca ou apenas quando enviar audio.
- Versao da palavra biblica.
- Nivel de detalhe do resumo.
- Integracoes ligadas ou desligadas.
- Horarios de silencio.

### Configuracao inicial sugerida

- Resumo da manha em dias uteis: 5:45.
- Palavra biblica em dias uteis: junto do resumo da manha.
- Lembrete de saida para o trabalho: 7:10.
- Checagem rapida no almoco: 12:10.
- Checagem de volta para casa: 17:15.
- Planejamento de estudo/projetos: 18:10.
- Quarta e sexta: aviso da igreja as 18:50.
- Resumo da manha no sabado: 9:30.
- Resumo da manha no domingo: 9:30.
- Aviso da igreja no domingo: 17:15.
- Atualizacoes de hora em hora: somente quando houver compromisso, estudo, tarefa importante ou algo pendente.
- Duracao padrao de bloco de estudo: 90 minutos.
- Eventos da agenda: o bot pode criar automaticamente, mantendo possibilidade de edicao pelo usuario.

## Primeira versao recomendada

Para evitar complexidade excessiva, a primeira versao deve ter:

1. Bot do Telegram por texto.
2. Audio recebido com transcricao.
3. Resposta em audio.
4. Lembretes em SQLite.
5. Resumo diario as 7:20 em dias uteis.
6. Horario diferente no fim de semana.
7. Memoria simples e editavel.
8. Planejamento semanal na segunda de manha.

Depois entram:

1. Google Calendar.
2. Gmail.
3. Resumos inteligentes de email.
4. Painel web.
5. Integracoes extras com telefone.

## Perguntas para configurar sua rotina

1. A janela de almoco vai normalmente ate 13:30?
2. Em qual pasta do PC ficam seus projetos principais?
3. Voce prefere que o assistente cobre com firmeza ou fale de um jeito mais leve?
4. Voce quer que ele leia todos os emails ou somente emails importantes/marcados?
5. Alem de quarta, sexta e domingo, existe algum compromisso fixo?
