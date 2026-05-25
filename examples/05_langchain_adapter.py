"""LangChain adapter for Hebb Mind — SKELETON.

# WIP — contributions welcome — see issue #TBD
#
# A starting point, not a finished integration. Two natural plug points:
#   (a) BaseChatMessageHistory — durable backing store for a conversation
#       thread, so any `RunnableWithMessageHistory` chain remembers.
#   (b) BaseRetriever — expose Hebb Mind search to RAG / agent-tool chains.
#
# Done: class skeletons + signatures.
# TODO: serialization, partition routing, async paths, tests, an example.
# Good first PR: finish (b) end-to-end plus a 30-line example chain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hebb import HebbMind

if TYPE_CHECKING:
    # Avoid hard dependency on langchain at import time.
    from langchain_core.documents import Document
    from langchain_core.messages import BaseMessage


class HebbChatMessageHistory:
    """Persist a single LangChain conversation to Hebb Mind.

    Intended subclass of ``langchain_core.chat_history.BaseChatMessageHistory``.
    We don't subclass directly so this file imports without LangChain installed.

    TODO:
      * Decide on a stable serialization for tool calls / multimodal parts.
      * Map a session_id to a Hebb Mind partition or tag.
      * Implement async ``aadd_messages`` / ``aget_messages``.
    """

    def __init__(self, session_id: str, hc: HebbMind | None = None) -> None:
        self.session_id = session_id
        self.hc = hc or HebbMind()

    @property
    def messages(self) -> list[BaseMessage]:
        """Load all messages for this session from Hebb Mind."""
        raise NotImplementedError("WIP — see module docstring.")

    def add_messages(self, messages: list[BaseMessage]) -> None:
        """Append a batch of LangChain messages."""
        raise NotImplementedError("WIP — see module docstring.")

    def clear(self) -> None:
        """Delete every memory tied to this session_id."""
        raise NotImplementedError("WIP — see module docstring.")


class HebbRetriever:
    """Wrap Hebb Mind search as a LangChain retriever.

    Intended subclass of ``langchain_core.retrievers.BaseRetriever``.
    """

    def __init__(self, hc: HebbMind | None = None, top_k: int = 5) -> None:
        self.hc = hc or HebbMind()
        self.top_k = top_k

    def _get_relevant_documents(self, query: str, **_: Any) -> list[Document]:
        """Synchronous retrieval. TODO: implement async variant."""
        raise NotImplementedError("WIP — see module docstring.")


def main() -> None:
    print(__doc__)
    print("This file is a skeleton. See the module docstring for what to build.")


if __name__ == "__main__":
    main()
