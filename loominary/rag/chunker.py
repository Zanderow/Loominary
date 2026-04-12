"""Fixed-window token chunker using the BGE-M3 tokenizer.

Chunks are returned with character offsets so callers can store char_start/end
in the Qdrant payload for citation purposes.

The text is tokenized in segments of up to ``model_max_length`` characters at a
time so the tokenizer never sees a sequence longer than the model supports,
which avoids the "Token indices sequence length is longer than the specified
maximum sequence length" warning.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from loominary import config


@dataclass
class Chunk:
    index: int
    text: str
    char_start: int
    char_end: int
    token_count: int


_tokenizer = None

# Tokenize the text in character windows of this size.  Chosen so that each
# window produces well under 8192 tokens (the BGE-M3 limit).
_CHAR_WINDOW = 16_000


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        from transformers import AutoTokenizer
        _tokenizer = AutoTokenizer.from_pretrained(
            config.EMBED_MODEL_PATH,
            model_max_length=10**7,
        )
    return _tokenizer


def _tokenize_in_segments(text: str, tok):
    """Tokenize *text* in overlapping character windows to avoid exceeding
    the model's maximum sequence length.  Returns combined (input_ids, offsets)
    lists covering the entire text."""
    all_ids: list[int] = []
    all_offsets: list[tuple[int, int]] = []

    char_overlap = 200
    pos = 0
    while pos < len(text):
        end = min(pos + _CHAR_WINDOW, len(text))
        segment = text[pos:end]
        enc = tok(
            segment,
            add_special_tokens=False,
            return_offsets_mapping=True,
            truncation=False,
        )
        seg_ids = enc["input_ids"]
        seg_off = enc["offset_mapping"]

        if pos == 0:
            all_ids.extend(seg_ids)
            all_offsets.extend((s + pos, e + pos) for s, e in seg_off)
        else:
            # Skip tokens that overlap with the previous window.
            for i, (s, _e) in enumerate(seg_off):
                char_abs = s + pos
                if all_offsets and char_abs <= all_offsets[-1][1]:
                    continue
                all_ids.extend(seg_ids[i:])
                all_offsets.extend((s + pos, e + pos) for s, e in seg_off[i:])
                break

        if end == len(text):
            break
        pos += _CHAR_WINDOW - char_overlap

    return all_ids, all_offsets


def chunk_text(
    text: str,
    chunk_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> List[Chunk]:
    """Split *text* into fixed-size token windows with overlap."""
    chunk_tokens = chunk_tokens or config.RAG_CHUNK_TOKENS
    overlap_tokens = overlap_tokens or config.RAG_CHUNK_OVERLAP

    if not text.strip():
        return []

    tok = _get_tokenizer()
    input_ids, offsets = _tokenize_in_segments(text, tok)

    if not input_ids:
        return []

    step = max(1, chunk_tokens - overlap_tokens)
    chunks: List[Chunk] = []
    idx = 0
    start = 0
    n = len(input_ids)
    while start < n:
        end = min(start + chunk_tokens, n)

        char_start = offsets[start][0]
        char_end = offsets[end - 1][1]
        if char_end == 0:
            char_end = len(text)

        piece = text[char_start:char_end].strip()
        if piece:
            chunks.append(
                Chunk(
                    index=idx,
                    text=piece,
                    char_start=char_start,
                    char_end=char_end,
                    token_count=end - start,
                )
            )
            idx += 1
        if end == n:
            break
        start += step
    return chunks
