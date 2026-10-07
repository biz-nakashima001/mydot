# MyDot

自宅Ubuntu Server上で常時稼働するパーソナルAIエージェント。

## Architecture

Windows / Browser / Microphone
        |
        | HTTPS
        v
Tailscale Serve
        |
        v
FastAPI
        |
        v
MyDot
        |
        +-- LOCAL --> Ollama / qwen3:8b
        |
        +-- CODE  --> OpenAI Codex CLI
                         |
                         v
                  workspace/

## Current Features

- FastAPI Web Chat
- Markdown rendering
- Browser voice input
- Tailscale HTTPS access
- Ollama / Codex task routing
- qwen3:8b local inference
- Codex workspace-write execution
- systemd auto startup
- Ollama model warmup on boot
- qwen3:8b keep_alive=-1

## Services

- `mydot.service`
  - MyDot background daemon

- `mydot-api.service`
  - FastAPI / Uvicorn Web interface

- `mydot-warmup.service`
  - Waits for Ollama API after boot
  - Loads qwen3:8b into GPU memory
  - Keeps model resident

- `ollama.service`
  - Local LLM server

- `tailscaled.service`
  - Tailscale network

## Web Access

Access MyDot through Tailscale Serve HTTPS.

The FastAPI application itself listens on:

`http://localhost:8080`

Tailscale Serve proxies HTTPS traffic to FastAPI.

## Task Routing

### LOCAL

Questions, explanations, summaries and lightweight reasoning.

MyDot -> Ollama -> qwen3:8b

### CODE

File operations, programming, shell/system operations.

MyDot -> Codex CLI -> workspace

Codex working directory:

`~/mydot/workspace`

Codex runs with:

`--sandbox workspace-write`

## Boot Sequence

Ubuntu Server
    |
    +-- ollama.service
    |
    +-- mydot-warmup.service
    |       |
    |       +-- wait for Ollama API
    |       +-- load qwen3:8b
    |       +-- keep_alive=-1
    |
    +-- mydot.service
    |
    +-- mydot-api.service
    |
    +-- tailscaled.service

After boot, MyDot is ready without manually starting services.

## Verified

Reboot test completed successfully.

- MyDot: active
- MyDot API: active
- MyDot warmup: active
- Ollama: active
- Tailscale: active
- qwen3:8b: 100% GPU / Forever
- Browser voice input: OK
- LOCAL route: OK
- CODE route: OK
- Codex workspace file creation: OK

## Future

- Conversation history / short-term memory
- Dify / RAG KNOWLEDGE route
- Text-to-speech
- Wake word ("MyDot")
- Smartphone UI
- Improved authentication and security
