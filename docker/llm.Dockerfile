# llama.cpp server with Qwen3.5-35B-A3B MXFP4 GGUF baked in.
# CPU build — see docker-compose.gpu.yml for CUDA override.
FROM ghcr.io/ggml-org/llama.cpp:server AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L -o /models/qwen3.5-35b-a3b.gguf \
    "https://huggingface.co/unsloth/Qwen3.5-35B-A3B-GGUF/resolve/main/Qwen3.5-35B-A3B-MXFP4_MOE.gguf?download=true"

EXPOSE 8080

ENTRYPOINT ["/llama-server"]
CMD [ \
    "--model", "/models/qwen3.5-35b-a3b.gguf", \
    "--host", "0.0.0.0", \
    "--port", "8080", \
    "--ctx-size", "8192", \
    "--threads", "4", \
    "--parallel", "1" \
]
