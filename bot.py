#!/usr/bin/env python3
"""Print messages sent with /msg to the terminal.

The bot uses Telegram's long-polling HTTP API, so it does not need a public
web server or third-party Python packages.
"""

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from agent import *

POLL_TIMEOUT_SECONDS = 30
TOKEN_FILE = Path(__file__).with_name("telegram_token.txt")
MAX_TELEGRAM_MESSAGE_LENGTH = 4096


def telegram_call(token: str, method: str, parameters: dict | None = None) -> dict:
    """Call a Telegram Bot API method and return its result."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = json.dumps(parameters or {}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=POLL_TIMEOUT_SECONDS + 10) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram API request failed"))
    return result["result"]


def send_text(token: str, chat_id: int, text: str) -> None:
    """Send text to Telegram, splitting long command output if necessary."""
    for start in range(0, len(text), MAX_TELEGRAM_MESSAGE_LENGTH):
        telegram_call(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text[start : start + MAX_TELEGRAM_MESSAGE_LENGTH],
            },
        )


def standard_sequence(message, parts):
    content = parts[1] if len(parts) == 2 else "(no text)"
    sender = message.get("from", {})
    name = sender.get("username") or " ".join(
        value for value in (sender.get("first_name"), sender.get("last_name")) if value
    ) or "unknown user"
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    #print(f"[{timestamp}] {name}: {content}", flush=True)
    return name, timestamp
'''
def print_msg(message: dict, token: str) -> None:
    """Handle /msg and /cmd messages."""
    text = message.get("text", "")
    parts = text.split(maxsplit=1)
    command = parts[0].split("@", maxsplit=1)[0].lower() if parts else ""

    if command == "/msg":
        content = parts[1] if len(parts) == 2 else "(no text)"
        name, timestamp = standard_sequence(message, parts)
        print(f"[{timestamp}] {name}: {content}", flush=True)

    elif command == "/cmd":
        content = parts[1] if len(parts) == 2 else "(no text)"
        name, timestamp = standard_sequence(message, parts)

        # Save output of the executed command to a variable and print it.
        result = subprocess.run(content, shell=True, capture_output=True, text=True)
        command_output = result.stdout
        if result.stderr:
           command_output += f"\n[stderr]\n{result.stderr}"
        if not command_output:
            command_output = "(no output)"
        if result.returncode != 0:
            command_output += f"\n[exit code: {result.returncode}]"

        print(f"[{timestamp}] {name}: Executed command: {content}", flush=True)
        print(f"Command output:\n{command_output}", flush=True)

        # Send the saved output back to the Telegram chat that issued /cmd.
        send_text(token, message["chat"]["id"], command_output)

    elif command == "/agent":
            content = parts[1] if len(parts) == 2 else "(no text)"
            name, timestamp = standard_sequence(message, parts)
            agent_response = prompt_agent(content)
            print(f"[{timestamp}] {name}: Prompted agent with: {content}", flush=True)
            print(f"Agent response:\n{agent_response}", flush=True)
            send_text(token, message["chat"]["id"], agent_response)
    else:
        return  # Ignore other messages
'''

def handle_msg(message: dict, token: str) -> None:
    """Handle /msg and /cmd messages."""
    text = message.get("text", "")
    parts = text.split(maxsplit=1)       
    content = parts[1] if len(parts) == 2 else "(no text)"
    name, timestamp = standard_sequence(message, parts)
    print(f"[{timestamp}] {name}: {content}", flush=True)

def handle_cmd(message: dict, token: str) -> None:
    """Handle /cmd messages."""
    text = message.get("text", "")
    parts = text.split(maxsplit=1)       
    content = parts[1] if len(parts) == 2 else "(no text)"
    name, timestamp = standard_sequence(message, parts)
    # Save output of the executed command to a variable and print it.
    result = subprocess.run(content, shell=True, capture_output=True, text=True)
    command_output = result.stdout
    if result.stderr:
       command_output += f"\n[stderr]\n{result.stderr}"
    if not command_output:
        command_output = "(no output)"
    if result.returncode != 0:
        command_output += f"\n[exit code: {result.returncode}]"

        print(f"[{timestamp}] {name}: Executed command: {content}", flush=True)
        print(f"Command output:\n{command_output}", flush=True)
        # Send the saved output back to the Telegram chat that issued /cmd.
        send_text(token, message["chat"]["id"], command_output)

def handle_agent(message: dict, token: str) -> None:
    """Handle /agent messages."""
    text = message.get("text", "")
    parts = text.split(maxsplit=1)       
    content = parts[1] if len(parts) == 2 else "(no text)"
    name, timestamp = standard_sequence(message, parts)
    agent_response = prompt_agent(content)
    print(f"[{timestamp}] {name}: Prompted agent with: {content}", flush=True)
    print(f"Agent response:\n{agent_response}", flush=True)
    send_text(token, message["chat"]["id"], agent_response)



def print_msg_switch_case(message: dict, token: str) -> None:
    text = message.get("text", "")
    command = text.split(maxsplit=1)[0].split("@", 1)[0].lower()

    cases = {
        "/msg": lambda: handle_msg(message, token),
        "/cmd": lambda: handle_cmd(message, token),
        "/agent": lambda: handle_agent(message, token),
    }

    handler = cases.get(command)

    if handler:
        handler()




def main() -> None:
    try:
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError as error:
        sys.exit(f"Could not read {TOKEN_FILE.name}: {error}")

    if not token or "PASTE_YOUR_BOT_TOKEN_HERE" in token:
        sys.exit(f"Put your token from @BotFather in {TOKEN_FILE.name} first.")

    try:
        bot = telegram_call(token, "getMe")
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        sys.exit(f"Could not connect to Telegram: {error}")

    print(f"Listening as @{bot.get('username', 'your bot')}. Press Ctrl+C to stop.")
    offset = None

    while True:
        parameters = {
            "timeout": POLL_TIMEOUT_SECONDS,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            parameters["offset"] = offset

        try:
            updates = telegram_call(token, "getUpdates", parameters)
            for update in updates:
                # Advance the offset before processing so Telegram does not
                # deliver this update again on the next poll.
                offset = update["update_id"] + 1
                message = update.get("message")
                if message:
                    print_msg_switch_case(message, token)
        except KeyboardInterrupt:
            print("\nStopped.")
            return
        except (OSError, RuntimeError, json.JSONDecodeError) as error:
            print(f"Telegram connection error: {error}. Retrying in 5 seconds.", file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    main()
