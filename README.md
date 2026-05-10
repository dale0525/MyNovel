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
pixi run test
pixi run lint
```

`pixi run dev` starts the local debug web server at `http://127.0.0.1:8765`.
The dev surface is localized in Simplified Chinese and asks for OpenAI-compatible
LLM/Embedding settings before enabling the open-book flow.

## License

Apache-2.0.
