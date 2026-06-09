# Companion Local AI vLLM RX7600 Failure Notes

Date: 2026-06-01

## Decision

OpenDAoC mercenary dialogue should not continue with vLLM on the RX7600 second PC. The next local AI runtime target is llama.cpp with Gemma 4 E4B GGUF.

## Hardware And Runtime

- Host: second PC, Linux, SSH alias `opendaoc-second`
- GPU: AMD Radeon RX 7600 8GB
- Runtime attempted: vLLM 0.22.0 on ROCm
- vLLM workspace during experiment: `/db/opendaoc-vllm`
- Failure log archive: `/db/opendaoc-ai-failure-archive/vllm/vllm-gemma4-rx7600-20260601-201810-logs.tar.gz`

## Attempts

### Qwen2.5 3B

`Qwen/Qwen2.5-3B-Instruct` loaded and served successfully as `local-qwen2.5-3b-instruct`, but throughput was too small for broad mercenary chat concurrency.

Observed limits:

- vLLM reported max concurrency for 1024 tokens: `1.19x`.
- 1 concurrent request: stable, about 2.8 seconds average latency.
- 2 concurrent requests: usable, about 4.0 seconds average latency.
- 4 concurrent requests: burst limit, about 6.0 seconds average latency and p95 near 7.9 seconds.
- 6 concurrent requests: 5 of 6 timed out at 120 seconds.
- 8 concurrent requests: queued for several minutes with GPU saturated.

Quality issue:

- Korean output generally worked, but Hanja occasionally appeared in Korean text, e.g. `신원不明`.

### Gemma 4 E4B GGUF With TurboQuant

Model:

- `/db/opendaoc-vllm/models/gemma-4-E4B-it-GGUF/gemma-4-E4B-it-Q4_K_S.gguf`
- tokenizer / config: `google/gemma-4-E4B-it`

The TurboQuant attempt failed during engine initialization.

Representative error:

```text
ValueError: Selected backend AttentionBackendEnum.TURBOQUANT is not valid for this configuration. Reason: ['kv_cache_dtype not supported']
```

Conclusion:

- `--attention-backend TURBOQUANT` and `--kv-cache-dtype turboquant_k8v4` are invalid for this Gemma 4 E4B + ROCm + vLLM configuration.

### Gemma 4 E4B GGUF Without TurboQuant

Retried with:

- `--kv-cache-dtype auto`
- `--max-model-len 512`
- no explicit TurboQuant attention backend
- text-only multimodal limits

The server eventually opened `/v1/models`, but the model output was unusable.

Important log signal:

```text
OpenDAoC Gemma4 GGUF text loader left qkv uninitialized: [0, 1, 2, ..., 41]
```

Observed generation behavior:

- Chat completion spent completion tokens but returned an empty string.
- Completion endpoint returned unrelated fragments such as `طرح`.
- Chat endpoint returned unrelated fragments such as `mering`.

Conclusion:

- vLLM could start the Gemma 4 E4B GGUF server after removing TurboQuant, but the GGUF loader state was not valid enough for real Korean dialogue.
- This is not acceptable for mercenary dialogue or guide answers.

### Gemma 4 E4B AWQ

Model:

- `Chunity/gemma-4-E4B-it-AWQ-4bit`

The model was recognized as AWQ and vLLM enabled Triton AWQ on ROCm, but RX7600 8GB could not load it.

Representative error:

```text
torch.OutOfMemoryError: HIP out of memory. Tried to allocate 26.00 MiB.
GPU 0 has a total capacity of 7.98 GiB of which 0 bytes is free.
Of the allocated memory 7.74 GiB is allocated by PyTorch.
```

Conclusion:

- Gemma 4 E4B AWQ is too large for this RX7600 8GB vLLM setup.
- Lowering runtime context does not solve the model initialization footprint enough for safe use.

## Final Ruling

Do not spend more time on vLLM for Gemma 4 E4B on RX7600 8GB.

Use this vLLM work only as a failed experiment reference. For the next local mercenary AI runtime, start from llama.cpp because Gemma 4 E4B GGUF is closer to llama.cpp's normal support path than vLLM's GGUF loader path.

## Cleanup State

- vLLM processes were stopped.
- Port `8001` was closed after cleanup.
- RX7600 VRAM returned to idle.
- Failure logs were archived under `/db/opendaoc-ai-failure-archive/vllm/`.
- `/db/opendaoc-vllm` was removed after archiving the failure logs.
