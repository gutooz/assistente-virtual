# Assistente pessoal no Telegram

Primeira base do bot para organizar rotina, estudos, projetos, lembretes e agenda.

## O que ja esta preparado

- Configuracao inicial da rotina do usuario.
- Banco SQLite com memoria, estudos, eventos e lembretes.
- Conversa natural por texto para rotina, estudos, eventos e lembretes.
- Audio recebido com transcricao e resposta em audio.
- Descricao e comandos basicos configurados no perfil do bot.
- Registro de assuntos estudados com status.
- Estrutura para integrar Google Calendar e Gmail no futuro.

## Como configurar

1. Crie um bot no Telegram pelo BotFather.
2. Copie `.env.example` para `.env`.
3. Coloque `TELEGRAM_BOT_TOKEN` e `OPENAI_API_KEY`.
4. Para Google Calendar/Gmail, preencha tambem:

```env
GOOGLE_API_KEY=sua_api_key_google
GOOGLE_CLIENT_ID=seu_client_id_google
GOOGLE_CLIENT_SECRET=seu_client_secret_google
GOOGLE_TOKEN_PATH=google_token.json
```

Esses valores devem ficar apenas no `.env`, que ja esta no `.gitignore`.
5. Instale as dependencias:

```powershell
pip install -r requirements.txt
```

6. Rode o bot:

```powershell
python -m bot.main
```

## Comandos iniciais

Os comandos ficam como plano B. O uso principal e conversar naturalmente.

- `/inicio` - mostra o assistente.
- `/rotina` - mostra a rotina configurada.
- `/estudo assunto` - cria um estudo de 90 minutos.
- `/estudos` - lista estudos cadastrados.
- `/evento titulo | data/hora | descricao` - cadastra evento local.
- `/eventos` - lista eventos locais.
- `/lembretes` - lista lembretes.
- `/memoria` - mostra memorias salvas.
- `/config` - mostra configuracoes principais.

## Exemplos

```text
preciso estudar autenticacao OAuth do Google
marca reuniao amanha as 9h
me lembra de pagar a conta sexta as 18h
quero organizar minha semana
quero desenvolver meus projetos do PC
```

Tambem e possivel enviar audio. O bot transcreve, interpreta e responde com audio.
