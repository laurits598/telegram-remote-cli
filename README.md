# Telegram Remote CLI

A small, dependency-free Telegram bot for talking to a computer from anywhere Telegram is available.

The project currently has two intended uses:

- **A Telegram interface for a local LLM** — send prompts to an Ollama model running on the host with `/agent`.
- **A lightweight remote-access bridge** — send a command to the host with `/cmd` and receive its output in Telegram. `/msg` can be used for simple messages that are printed in the host's terminal.

## Why Telegram instead of SSH?

This bot uses Telegram's long polling API: the host makes an outbound HTTPS connection to Telegram and waits for messages. It does not need a public IP address, an open inbound port, port forwarding, or a webhook endpoint.

The usual networking terms for this situation are **behind NAT**, **behind a firewall**, **not publicly routable**, or **inbound-restricted**. In other words, the host can reach the internet but cannot accept a normal incoming SSH connection. This is a convenient workaround, not a replacement for a properly secured remote-access solution.

## Features

- Long polling; no web server or public endpoint required
- Uses only Python's standard library
- `/cmd` executes a shell command on the host and returns stdout/stderr
- `/agent` sends a prompt to a local Ollama server
- Long replies are split to fit Telegram's message-size limit
- Can run directly on the host or in Docker

## Requirements

- Python 3.10 or newer
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- Optional: [Ollama](https://ollama.com/) for `/agent`

## Quick start

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. Put the token in a local file named `telegram_token.txt`:

   ```text
   123456:your-token-from-botfather
   ```

   This file is ignored by Git. Never commit the real token.

3. Start the bot:

   ```bash
   python3 bot.py
   ```

4. Open a chat with the bot and send a command, for example:

   ```text
   /cmd uname -a
   ```

The terminal running the bot should show that it is listening as your bot. Stop it with `Ctrl+C`.

## Commands

| Command | Description | Example |
| --- | --- | --- |
| `/cmd <command>` | Execute a shell command on the host and send the result back to Telegram | `/cmd df -h` |
| `/msg <text>` | Print a message in the bot terminal | `/msg hello from Telegram` |
| `/agent <prompt>` | Ask the configured local Ollama model a question | `/agent summarize the latest log` |

Telegram bot commands can also include the bot's username, such as `/cmd@my_bot ls`.

## Local LLM setup

Install and start Ollama, then pull the model configured in `agent.py`:

```bash
ollama serve
ollama pull llama3.1:latest
python3 bot.py
```

By default, the bot connects to:

```text
http://localhost:11434/api/chat
```

Set `OLLAMA_URL` if Ollama is running somewhere else:

```bash
OLLAMA_URL=http://127.0.0.1:11434/api/chat python3 bot.py
```

## Docker

Build the image:

```bash
docker build -t telegram-remote-cli .
```

Run the bot with the token mounted read-only:

```bash
docker run -d \
  --name telegram-bot \
  --restart unless-stopped \
  -v "$PWD/telegram_token.txt:/app/telegram_token.txt:ro" \
  telegram-remote-cli
```

If Ollama is running on the Docker host, use the host gateway address and pass it to the container:

```bash
docker run -d \
  --name telegram-bot \
  --restart unless-stopped \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_URL=http://host.docker.internal:11434/api/chat \
  -v "$PWD/telegram_token.txt:/app/telegram_token.txt:ro" \
  telegram-remote-cli
```

## Security

Treat this bot as remote code execution on the machine where it runs. Anyone who can use the bot may be able to run commands as the bot process user.

- Restrict access to the bot with Telegram-side checks before using it on an important machine.
- Run it as an unprivileged user and use a dedicated environment where possible.
- Do not run it as root.
- Protect `telegram_token.txt`; anyone with the token can control the bot.
- Be careful with shell quoting, secrets in command output, and commands that modify or delete data.
- Consider this an experimental personal tool rather than a hardened administration service.

## Project layout

```text
bot.py       Telegram polling loop and command handling
agent.py     Ollama HTTP client and agent wrapper
Dockerfile   Minimal container image
```

## License

No license has been specified yet.
