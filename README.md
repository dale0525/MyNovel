# MyNovel

Local AI-led web novel production pipeline with human review gates.

## Status

Planning and early foundation work.

## Product Direction

MyNovel is not a text editor. It is a personal local AI web-novel production line:
AI plans, drafts, audits, revises, and maintains state; the author reviews and approves.

## Development

```bash
pixi run dev
pixi run preview
```

`pixi run dev` starts the local API server at `http://127.0.0.1:8765`
and the Vite frontend at `http://127.0.0.1:5173`. Open the Vite URL while
developing; frontend edits hot-reload there and `/api` requests are proxied to
the local API server.

`pixi run preview` rebuilds the frontend, copies it into the Python package, and
serves the packaged static preview at `http://127.0.0.1:8765`.

The dev surface is localized in Simplified Chinese and asks for OpenAI-compatible
LLM/Embedding settings before enabling the open-book flow.
Embedding and Rerank can reuse the LLM Base URL/API Key. The open-book flow only
requires one idea, then asks the configured LLM to generate and revise a structured
book blueprint.

CI and release checks live in `.github/workflows/` and call the underlying tools
directly through the pixi environment instead of relying on local convenience
task aliases.

## License

Apache-2.0.
