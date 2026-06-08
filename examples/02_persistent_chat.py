"""Persistent chat — an agent that remembers across runs.

A minimal CLI chat loop showing the canonical "memory framework" story:

    Each turn, the script searches Hebb Mind for context relevant to your
    new message, prepends the hits to the system prompt, calls the LLM via
    LiteLLM, and writes your message back to memory.

    Quit, run the script again — the agent still knows what you told it.

Run it
------

    # With a real LLM (set OPENAI_API_KEY or any LiteLLM-supported provider)
    python examples/02_persistent_chat.py

    # Pick a different model (LiteLLM model string)
    python examples/02_persistent_chat.py --model anthropic/claude-3-5-sonnet-latest

    # No API key? It still runs — using a local stub responder so you can see
    # the memory roundtrip end-to-end.
    python examples/02_persistent_chat.py

Type ``/quit`` (or hit Ctrl-D) to exit.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterable
from pathlib import Path

from hebb import HebbMind

DEFAULT_MODEL = "openai/gpt-4o-mini"
DEFAULT_HOME = Path("examples/data")
SYSTEM_PROMPT_BASE = (
    "You are a helpful assistant with persistent memory. Use the MEMORY block "
    "below to personalize answers. If a fact is missing, say so honestly."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"LiteLLM model id (default: {DEFAULT_MODEL}).")
    parser.add_argument("--home", type=Path,
                        default=Path(os.environ.get("HEBB_HOME", DEFAULT_HOME)),
                        help="Workspace directory for memory storage "
                             "(DB lives at <home>/hebb.db).")
    parser.add_argument("--top-k", type=int, default=5,
                        help="How many memories to inject as context per turn.")
    return parser.parse_args()


def has_any_llm_key() -> bool:
    """LiteLLM accepts many provider keys — true if at least one is set."""
    candidates = (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
        "AZURE_API_KEY", "GROQ_API_KEY", "TOGETHER_API_KEY",
        "MISTRAL_API_KEY", "COHERE_API_KEY", "OLLAMA_API_BASE",
    )
    return any(os.environ.get(k) for k in candidates)


def stub_response(user_msg: str, memory_snippets: Iterable[str]) -> str:
    """Offline fallback so the example works without an API key.

    Echoes the user, lists the memory snippets we *would have* sent to the LLM,
    and demonstrates that recall is functioning.
    """
    snippets = list(memory_snippets)
    if not snippets:
        return f"(stub) I have no memories yet relevant to: {user_msg!r}"
    bullets = "\n".join(f"  - {s}" for s in snippets)
    return (
        f"(stub) I would have answered using the LLM. Here is what I remembered:\n"
        f"{bullets}"
    )


def call_llm(model: str, system_prompt: str, history: list[dict]) -> str:
    """Route through LiteLLM. Imported lazily so the script imports cleanly."""
    from litellm import completion  # noqa: WPS433 — local import is intentional

    messages = [{"role": "system", "content": system_prompt}, *history]
    resp = completion(model=model, messages=messages)
    return resp["choices"][0]["message"]["content"]


def build_system_prompt(snippets: list[str]) -> str:
    if not snippets:
        return SYSTEM_PROMPT_BASE + "\n\nMEMORY: (empty)"
    block = "\n".join(f"- {s}" for s in snippets)
    return f"{SYSTEM_PROMPT_BASE}\n\nMEMORY:\n{block}"


def gather_memory_snippets(hc: HebbMind, query: str, top_k: int) -> list[str]:
    """Search Hebb Mind and return plain-text snippets for prompt injection."""
    hits = hc.search(query, top_k=top_k)
    snippets: list[str] = []
    for hit in hits:
        mem = getattr(hit, "memory", hit)
        snippets.append(mem.content)
    return snippets


def chat_loop(hc: HebbMind, model: str, top_k: int, online: bool) -> None:
    print(f"chat ready  (model={model if online else 'stub'}, top_k={top_k})")
    print("type /quit to exit, /forget to wipe memory.\n")
    history: list[dict] = []
    while True:
        try:
            user_msg = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            return
        if not user_msg:
            continue
        if user_msg in {"/quit", "/exit"}:
            print("bye.")
            return
        if user_msg == "/forget":
            # hc.list() returns a (memories, total) tuple — unpack it.
            all_mems, _ = hc.list()
            for mem in all_mems:
                hc.delete(mem.id)
            print("(memory wiped)")
            history.clear()
            continue

        # 1. Recall: search for context relevant to this user message.
        snippets = gather_memory_snippets(hc, user_msg, top_k)
        if snippets:
            print(f"  [recalled {len(snippets)} memory snippet(s)]")

        # 2. Generate a reply (real LLM or local stub).
        history.append({"role": "user", "content": user_msg})
        if online:
            try:
                reply = call_llm(model, build_system_prompt(snippets), history)
            except Exception as exc:  # noqa: BLE001 — surface the provider error
                reply = f"(LLM error: {exc!s})"
        else:
            reply = stub_response(user_msg, snippets)
        history.append({"role": "assistant", "content": reply})
        print(f"bot> {reply}\n")

        # 3. Write the user message to memory so it persists across runs.
        hc.add(user_msg, partition="mem_hippocampus", tags=["chat"])


def main() -> None:
    args = parse_args()
    args.home.mkdir(parents=True, exist_ok=True)
    # The facade resolves its workspace (and therefore the DB path) from HEBB_HOME.
    os.environ.setdefault("HEBB_HOME", str(args.home.resolve()))

    online = has_any_llm_key()
    if not online:
        print("No LLM API key detected — running with a local stub responder.",
              file=sys.stderr)
        print("Set OPENAI_API_KEY (or any LiteLLM-supported provider) to use a real model.\n",
              file=sys.stderr)

    hc = HebbMind()
    chat_loop(hc, model=args.model, top_k=args.top_k, online=online)


if __name__ == "__main__":
    main()
