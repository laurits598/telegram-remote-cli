# Telegram `/msg` printer

This small bot prints the text after `/msg` in the terminal where `bot.py` is running.
It also executes commands sent with `/cmd` and sends their output back to the Telegram chat.

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) in Telegram and copy its token.
2. Open `telegram_token.txt` and replace its placeholder with the token.

   ```text
   123456:your-token-from-botfather
   ```

3. Start the bot:

   ```bash
   python3 bot.py
   ```

4. Open a chat with the bot and send a message such as:

   ```text
   /msg hello from Telegram
   ```

   To execute a command and receive its output in Telegram, send:

   ```text
   /cmd ls
   ```

The running terminal will print something like:

```text
[2026-09-21 16:00:00] alice: hello from Telegram
```

Stop the program with `Ctrl+C`. The program uses only Python's standard library.
