"""
A very simple Python wrapper around a local Ollama agent.

Requires: Ollama running locally (`ollama serve`) and a pulled model,
e.g. `ollama pull llama3.2`.

No third-party dependencies - uses only the standard library.
"""

import json
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.1:latest"


def ask(prompt: str, model: str = MODEL, system: str | None = None) -> str:
    """Send `prompt` to the Ollama model and return its answer as a string."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return data["message"]["content"]


class Agent:
    """Same thing, but remembers the conversation."""

    def __init__(self, model: str = MODEL, system: str | None = None):
        self.model = model
        self.history = []
        if system:
            self.history.append({"role": "system", "content": system})

    def ask(self, prompt: str) -> str:
        self.history.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": self.model,
            "messages": self.history,
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        answer = data["message"]["content"]
        self.history.append({"role": "assistant", "content": answer})
        return answer

def prompt_agent(prompt: str, model: str = MODEL, system: str | None = None) -> str:
    """Prompt the Ollama agent and return its answer."""
    agent = Agent(model=model, system=system)
    return agent.ask(prompt)


#if __name__ == "__main__":
#    # Prompt the agent on startup and keep the reply in a variable.
#    answer = ask("In one sentence: what is a rubber duck used for in programming?")
#    print(answer)

    # Stateful version:
    # agent = Agent(system="You answer in exactly one short sentence.")
    # first = agent.ask("Name a prime number between 10 and 20.")
    # second = agent.ask("Now double it.")
    # print(first, "|", second)