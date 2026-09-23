"""
A simple Python wrapper around a local Ollama agent, with filesystem tools.

The agent can list directories, search for files, read files and report file
info - so you can ask "what's in the working directory?" or "where's config.yaml?"
and it will actually go look.

Requires Ollama running locally (`ollama serve`) and a pulled model.
Standard library only - no pip installs.

Run it:
    python ollama_agent.py                  # runs the demo below
    python ollama_agent.py "where is X?"    # one-off question
    python ollama_agent.py -i               # interactive chat
    python ollama_agent.py -m llama3.1 -i   # pick a model
"""

import fnmatch
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

HOST = "http://localhost:11434"
MODEL = "qwen2.5-coder:7b"      # a tool-capable model; change to what you have


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             ".mypy_cache", ".pytest_cache", "dist", "build", ".idea"}


class FileTools:
    """Filesystem tools, sandboxed to `root`."""

    def __init__(self, root: str = "."):
        self.root = Path(root).expanduser().resolve()

    def _safe(self, path: str) -> Path:
        p = (self.root / (path or ".")).expanduser().resolve()
        if p != self.root and self.root not in p.parents:
            raise ValueError(f"path outside the allowed root: {p}")
        return p

    def list_dir(self, path: str = ".") -> str:
        p = self._safe(path)
        if not p.is_dir():
            return f"Not a directory: {p}"
        lines = []
        for e in sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower())):
            lines.append(f"{e.name}/" if e.is_dir()
                         else f"{e.name}  ({e.stat().st_size} bytes)")
        return f"Contents of {p}:\n" + ("\n".join(lines) or "(empty)")

    def find_files(self, pattern: str, path: str = ".", max_results: int = 50) -> str:
        start = self._safe(path)
        pat = pattern if any(c in pattern for c in "*?[") else f"*{pattern}*"
        hits = []
        for dirpath, dirnames, filenames in os.walk(start):
            dirnames[:] = [d for d in dirnames
                           if d not in SKIP_DIRS and not d.startswith(".")]
            for name in list(dirnames) + filenames:
                if fnmatch.fnmatch(name.lower(), pat.lower()):
                    hits.append(str(Path(dirpath) / name))
                    if len(hits) >= max_results:
                        break
            if len(hits) >= max_results:
                break
        if not hits:
            return f"No matches for '{pattern}' under {start}"
        return f"Matches for '{pattern}' under {start}:\n" + "\n".join(hits)

    def read_file(self, path: str, max_bytes: int = 4000) -> str:
        p = self._safe(path)
        if not p.is_file():
            return f"Not a file: {p}"
        return f"--- {p} ---\n{p.read_text(errors='replace')[:max_bytes]}"

    def file_info(self, path: str) -> str:
        p = self._safe(path)
        if not p.exists():
            return f"Does not exist: {p}"
        st = p.stat()
        return (f"{p}\ntype: {'directory' if p.is_dir() else 'file'}\n"
                f"size: {st.st_size} bytes\nmodified: {st.st_mtime}")

    # Schema advertised to the model (native Ollama tool-calling format).
    SCHEMA = [
        {"type": "function", "function": {
            "name": "list_dir",
            "description": "List the files and subdirectories of a directory.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "Directory path. Default '.'"}}}}},
        {"type": "function", "function": {
            "name": "find_files",
            "description": ("Recursively search for files or directories by name. "
                            "Accepts a glob like '*.py' or a substring like 'config'."),
            "parameters": {"type": "object", "properties": {
                "pattern": {"type": "string", "description": "Glob or substring."},
                "path": {"type": "string", "description": "Where to search. Default '.'"}},
                "required": ["pattern"]}}},
        {"type": "function", "function": {
            "name": "read_file",
            "description": "Read the beginning of a text file.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"}}, "required": ["path"]}}},
        {"type": "function", "function": {
            "name": "file_info",
            "description": "Size, type and modification time of a file or directory.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"}}, "required": ["path"]}}},
    ]


# --------------------------------------------------------------------------
# Prompts
# --------------------------------------------------------------------------

BASE_RULES = """You are an assistant running INSIDE a Python program on the user's
computer. You DO have access to their filesystem through tools. Never claim you
cannot see files - you can. When asked about files or directories, use a tool to
look it up rather than guessing, and report full paths."""

# Extra instructions for models that don't support native tool calling.
TEXT_PROTOCOL = """
To use a tool, reply with NOTHING but a single JSON object:
{"tool": "<name>", "args": {...}}

Available tools:
  list_dir   {"path": "."}                     - list a directory
  find_files {"pattern": "config", "path": "."} - recursive search by name
  read_file  {"path": "notes.txt"}             - read a text file
  file_info  {"path": "notes.txt"}             - size/type/modified

The program runs the tool and sends you the result. Then either call another
tool the same way, or give your final answer as plain text (no JSON).
"""


# --------------------------------------------------------------------------
# Agent
# --------------------------------------------------------------------------

class Agent:
    def __init__(self, model: str = MODEL, root: str = ".", host: str = HOST,
                 verbose: bool = True, max_steps: int = 8, mode: str = "auto"):
        self.model = model
        self.host = host.rstrip("/")
        self.tools = FileTools(root)
        self.verbose = verbose
        self.max_steps = max_steps
        self.mode = mode                # "auto" | "native" | "text"
        self.history = []
        self._set_system()

    # --- setup ------------------------------------------------------------

    def _set_system(self):
        sys_msg = f"{BASE_RULES}\n\nThe working directory is: {self.tools.root}"
        if self.mode == "text":
            sys_msg += "\n" + TEXT_PROTOCOL
        if self.history and self.history[0]["role"] == "system":
            self.history[0]["content"] = sys_msg
        else:
            self.history.insert(0, {"role": "system", "content": sys_msg})

    def _post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(
            f"{self.host}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _detect_mode(self):
        """Ask the model to make one tool call; if it can't, fall back to text mode."""
        probe = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Use the provided tool."},
                {"role": "user", "content": "List the current directory using list_dir."},
            ],
            "tools": FileTools.SCHEMA,
            "stream": False,
        }
        try:
            msg = self._post("/api/chat", probe).get("message", {})
            native = bool(msg.get("tool_calls"))
        except urllib.error.HTTPError:
            native = False          # server rejected the `tools` field entirely
        self.mode = "native" if native else "text"
        self._set_system()
        if self.verbose:
            note = "native tool calling" if native else \
                   "JSON text protocol (model has no native tool support)"
            print(f"[agent] model={self.model}  mode={note}")

    # --- tool execution ---------------------------------------------------

    def _run_tool(self, name: str, args: dict) -> str:
        fn = getattr(self.tools, name, None)
        if fn is None or name.startswith("_"):
            return f"Unknown tool: {name}"
        try:
            return fn(**args)
        except Exception as exc:
            return f"Error running {name}: {exc}"

    @staticmethod
    def _extract_call(text: str):
        """Pull a {"tool": ..., "args": ...} object out of a plain-text reply."""
        if not text:
            return None
        # strip ```json fences if present
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
        candidate = fenced.group(1) if fenced else None
        if candidate is None:
            start = text.find("{")
            if start == -1:
                return None
            depth, end = 0, None
            for i, ch in enumerate(text[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end is None:
                return None
            candidate = text[start:end]
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        if isinstance(obj, dict) and "tool" in obj:
            args = obj.get("args") or obj.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            return obj["tool"], args
        return None

    # --- main entry point -------------------------------------------------

    def ask(self, prompt: str) -> str:
        """Send a prompt, let the model use tools as needed, return the answer."""
        if self.mode == "auto":
            self._detect_mode()

        self.history.append({"role": "user", "content": prompt})

        for _ in range(self.max_steps):
            body = {"model": self.model, "messages": self.history, "stream": False}
            if self.mode == "native":
                body["tools"] = FileTools.SCHEMA
            msg = self._post("/api/chat", body).get("message", {})
            self.history.append(msg)

            calls = msg.get("tool_calls") or []
            if calls:                                    # native tool calling
                for call in calls:
                    name = call["function"]["name"]
                    args = call["function"].get("arguments") or {}
                    if isinstance(args, str):
                        args = json.loads(args)
                    if self.verbose:
                        print(f"  [tool] {name}({args})")
                    self.history.append({"role": "tool", "name": name,
                                         "content": self._run_tool(name, args)})
                continue

            content = msg.get("content", "")
            parsed = self._extract_call(content) if self.mode == "text" else None
            if parsed:                                   # text protocol
                name, args = parsed
                if self.verbose:
                    print(f"  [tool] {name}({args})")
                self.history.append({"role": "user",
                                     "content": f"Tool result:\n{self._run_tool(name, args)}"})
                continue

            return content

        return "(stopped: too many tool steps)"


# Module-level convenience: one shared agent rooted at the current directory.
_default = None


def ask(prompt: str, root: str = ".", model: str = MODEL) -> str:
    """One-liner: ask("...") -> answer string."""
    global _default
    if _default is None:
        _default = Agent(model=model, root=root)
    return _default.ask(prompt)


def list_models(host: str = HOST):
    """Names of the models installed in Ollama."""
    with urllib.request.urlopen(f"{host.rstrip('/')}/api/tags") as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [m["name"] for m in data.get("models", [])]


# --------------------------------------------------------------------------
# CLI / demo
# --------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    model = MODEL
    if "-m" in args:
        i = args.index("-m")
        model = args[i + 1]
        del args[i:i + 2]

    try:
        installed = list_models()
    except Exception:
        print("Could not reach Ollama at " + HOST + " - is `ollama serve` running?")
        return
    if model not in installed:
        print(f"Model '{model}' is not installed. Installed: {installed or '(none)'}")
        print(f"Either `ollama pull {model}` or run with -m <one of the above>.")
        if not installed:
            return
        model = installed[0]
        print(f"Falling back to '{model}'.\n")

    agent = Agent(model=model, root=".")

    if args and args[0] in ("-i", "--interactive"):
        print("Type a question, or 'quit'.")
        while True:
            try:
                q = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if q.lower() in {"quit", "exit", "q"}:
                break
            if q:
                print(agent.ask(q))
        return

    if args:
        print(agent.ask(" ".join(args)))
        return

    # --- demo: make it inspect the working directory ---------------------
    answer = agent.ask("Check the /mnt/c/users/lauri/Desktop/ directory and tell me what files are in it.")
    print("\nANSWER:", answer)

    follow_up = agent.ask("Now find any Python files anywhere below it.")
    print("\nANSWER:", follow_up)


if __name__ == "__main__":
    main()