# Loominary app — bakes BGE-M3 + BM25 weights for fully-offline use.
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libportaudio2 \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

# ----- bake embedding model weights -----
FROM base AS model-dl

RUN uv run python -c "\
from huggingface_hub import snapshot_download; \
snapshot_download('BAAI/bge-m3', local_dir='/models/bge-m3'); \
"

RUN uv run python -c "\
from fastembed import SparseTextEmbedding; \
SparseTextEmbedding(model_name='Qdrant/bm25'); \
"

# ----- final image -----
FROM base AS runtime

COPY --from=model-dl /models/bge-m3 /models/bge-m3
COPY --from=model-dl /root/.cache/fastembed /root/.cache/fastembed

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    EMBED_MODEL_PATH=/models/bge-m3 \
    QDRANT_URL=http://qdrant:6333 \
    LLM_BASE_URL=http://llm:8080

CMD ["uv", "run", "python", "main.py"]
