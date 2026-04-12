"""Chat with llama.cpp server (OpenAI-compatible endpoint).

Retrieves context, builds a grounded prompt with citations, and streams the
response back.

Qwen3.5 uses extended thinking — the model emits ``reasoning_content`` tokens
(chain-of-thought) before the visible ``content`` answer.  We show reasoning
dimmed so the user knows the model is working, then show the answer normally.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

import httpx

from loominary import config
from loominary.rag.retriever import hybrid_search


SYSTEM_PROMPT = """\
You are Loominary, a knowledgeable assistant. Answer the user's question \
using ONLY the numbered excerpts below. If none of the excerpts contain \
relevant information, say you don't have enough context.

Cite your sources by referencing the excerpt numbers in square brackets, \
e.g. [1], [3]. Place citations inline, immediately after the claim they support.

Be concise. Do not reproduce the excerpts verbatim unless the user asks for a quote. /no_think\
"""


def _build_context_block(hits: List[Dict[str, Any]]) -> str:
    parts = []
    for i, hit in enumerate(hits, 1):
        source = _source_label(hit)
        text = hit.get("text", "")
        parts.append(f"[{i}] {source}\n{text}")
    return "\n\n".join(parts)


def _source_label(hit: Dict[str, Any]) -> str:
    if hit.get("source_type") == "podcast":
        show = hit.get("show_name", "Unknown show")
        ep = hit.get("episode_title", "Unknown episode")
        date = hit.get("release_date", "")
        label = f"({show} — {ep}"
        if date:
            label += f", {date}"
        return label + ")"
    name = hit.get("meeting_name", "Unknown meeting")
    date = hit.get("start_time", "")
    label = f"({name}"
    if date:
        label += f", {date}"
    return label + ")"


@dataclass
class ChatStream:
    """Wraps an LLM streaming response + the citation hits it was based on.

    Yields ``(phase, text)`` tuples where *phase* is ``"thinking"`` or
    ``"answering"`` so the CLI can style them differently.
    """
    hits: List[Dict[str, Any]] = field(default_factory=list)
    _token_iter: Optional[Iterator[Tuple[str, str]]] = field(default=None, repr=False)

    def __iter__(self) -> Iterator[Tuple[str, str]]:
        if self._token_iter is not None:
            yield from self._token_iter


def ask(
    question: str,
    *,
    source_type: Optional[str] = None,
) -> ChatStream:
    hits = hybrid_search(query=question, source_type=source_type)
    context_hits = hits[: config.RAG_CONTEXT_K]

    if not context_hits:
        stream = ChatStream(hits=[])
        stream._token_iter = iter(
            [("answering", "I couldn't find any relevant excerpts in your library for that question.")]
        )
        return stream

    stream = ChatStream(hits=context_hits)
    stream._token_iter = _stream_llm(question, context_hits)
    return stream


def _stream_llm(
    question: str,
    context_hits: List[Dict[str, Any]],
) -> Iterator[Tuple[str, str]]:
    context = _build_context_block(context_hits)
    user_msg = f"--- EXCERPTS ---\n{context}\n\n--- QUESTION ---\n{question}"

    body = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": config.LLM_TEMPERATURE,
        "max_tokens": config.LLM_MAX_TOKENS,
        "stream": True,
    }

    url = config.LLM_BASE_URL.rstrip("/") + "/v1/chat/completions"
    with httpx.Client(timeout=300.0) as client:
        with client.stream("POST", url, json=body) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                chunk = json.loads(data)
                delta = chunk.get("choices", [{}])[0].get("delta", {})

                reasoning = delta.get("reasoning_content") or ""
                content = delta.get("content") or ""

                if reasoning:
                    yield ("thinking", reasoning)
                if content:
                    yield ("answering", content)


def format_sources(hits: List[Dict[str, Any]]) -> str:
    lines = []
    seen = set()
    for i, hit in enumerate(hits, 1):
        label = _source_label(hit)
        if label in seen:
            continue
        seen.add(label)
        lines.append(f"  [{i}] {label}")
    return "\n".join(lines)
