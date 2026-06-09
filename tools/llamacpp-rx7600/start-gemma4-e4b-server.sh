#!/usr/bin/env bash
set -euo pipefail

BASE="${OPENDAOC_LLAMACPP_BASE:-/db/opendaoc-llamacpp}"
HOST="${OPENDAOC_LLAMACPP_HOST:-0.0.0.0}"
PORT="${OPENDAOC_LLAMACPP_PORT:-8001}"
MODEL="${OPENDAOC_LLAMACPP_MODEL:-$BASE/models/gemma-4-E4B-it-GGUF/gemma-4-E4B-it-Q4_K_M.gguf}"
ALIAS="${OPENDAOC_LLAMACPP_ALIAS:-local-gemma-4-e4b-it}"
CTX_SIZE="${OPENDAOC_LLAMACPP_CTX_SIZE:-2048}"
PARALLEL="${OPENDAOC_LLAMACPP_PARALLEL:-4}"
THREADS="${OPENDAOC_LLAMACPP_THREADS:-6}"
THREADS_BATCH="${OPENDAOC_LLAMACPP_THREADS_BATCH:-$THREADS}"
GPU_LAYERS="${OPENDAOC_LLAMACPP_GPU_LAYERS:-999}"

export PATH="/opt/rocm/bin:$PATH"
export LD_LIBRARY_PATH="$BASE/llama.cpp/build/bin:/opt/rocm/lib:/opt/rocm/lib64:${LD_LIBRARY_PATH:-}"

# Do not set HSA_OVERRIDE_GFX_VERSION for RX7600/gfx1102 here.
# With llama.cpp built for gfx1102, the override caused Gemma4 slot initialization segfaults.
unset HSA_OVERRIDE_GFX_VERSION

exec "$BASE/llama.cpp/build/bin/llama-server" \
  -m "$MODEL" \
  --host "$HOST" \
  --port "$PORT" \
  --alias "$ALIAS" \
  --ctx-size "$CTX_SIZE" \
  --parallel "$PARALLEL" \
  --cont-batching \
  --n-gpu-layers "$GPU_LAYERS" \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --threads "$THREADS" \
  --threads-batch "$THREADS_BATCH" \
  --no-warmup \
  --reasoning off
