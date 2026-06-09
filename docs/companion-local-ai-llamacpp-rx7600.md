# Companion Local AI llama.cpp RX7600 Notes

Date: 2026-06-01

## Runtime

- Host: second PC, Linux, SSH alias `opendaoc-second`
- GPU: AMD Radeon RX 7600 8GB, ROCm `gfx1102`
- Runtime directory: `/db/opendaoc-llamacpp`
- Source: `ggml-org/llama.cpp`, build commit `5dcb711`
- Model: `ggml-org/gemma-4-E4B-it-GGUF/gemma-4-E4B-it-Q4_K_M.gguf`
- Served model alias: `local-gemma-4-e4b-it`
- OpenAI-compatible base URL: `http://192.168.0.28:8001`

## Build

llama.cpp was built with:

```bash
cmake -S . -B build -G Ninja \
  -DGGML_HIP=ON \
  -DAMDGPU_TARGETS=gfx1102 \
  -DCMAKE_BUILD_TYPE=Release \
  -DLLAMA_CURL=OFF
cmake --build build --config Release -j "$(nproc)" --target llama-server llama-cli
```

`cmake`, `ninja`, and `huggingface_hub[hf_xet]` are installed in `/db/opendaoc-llamacpp/venv`.

## Server Settings

The stable server settings are:

```bash
/db/opendaoc-llamacpp/start-gemma4-e4b-server-background.sh
```

Effective llama-server options:

- `--ctx-size 2048`
- `--parallel 4`
- `--cont-batching`
- `--n-gpu-layers 999`
- `--cache-type-k q8_0`
- `--cache-type-v q8_0`
- `--no-warmup`
- `--reasoning off`

Important: do not set `HSA_OVERRIDE_GFX_VERSION=11.0.0`. llama.cpp was built for `gfx1102`, and the override caused Gemma4 server slot initialization segfaults.

## Smoke Results

Single-slot and multi-slot generation succeeded through `/v1/chat/completions`.

- 2-client concurrent test, 6 requests: all succeeded, average latency about 0.71s, max about 1.03s, Hanja 0, broken text 0.
- 4-client concurrent test, 8 requests: all succeeded, average latency about 1.14s, max about 1.67s, Hanja 0, broken text 0.
- 8-client queued test against 4 server slots, 16 requests: all succeeded, average latency about 1.77s, max about 2.69s, Hanja 0, broken text 0.

Observed generation speed in server logs was about 22-26 tokens/sec per active slot for short Korean mercenary responses.

## Limits

The current `--ctx-size 2048 --parallel 4` setting gives each slot about 512 context tokens. This is good for short mercenary dialogue and persona replies. For longer RAG guide answers, restart with fewer slots and a larger context, for example `OPENDAOC_LLAMACPP_PARALLEL=2 OPENDAOC_LLAMACPP_CTX_SIZE=4096`.

## Gateway Routing

The recommended live AI gateway config is:

```powershell
$env:OPENDAOC_AI_GATEWAY_CONFIG = "tools/opendaoc-ai-gateway.hybrid-openai-local.json"
```

That config uses OpenAI small-model traffic first, local llama.cpp second, and Gemini last:

1. Rules and cache answer without any provider call.
2. `small-dialogue` and `openai-small-guide` use `openai/gpt-4.1-nano`.
3. OpenAI quota/rate/provider failures fall back to `local-gemma-4-e4b-it` through `http://192.168.0.28:8001`.
4. Gemini Flash-Lite is the emergency fallback after local fallback fails.

OpenAI Tier 3 data-sharing complimentary planning uses a 10M tokens/day small-model budget. Local `openai_compatible/` aliases are recorded as `unmetered_total_tokens` in the gateway ledger so local fallback does not consume or block the OpenAI daily complimentary budget.
