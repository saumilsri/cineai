# CineAI

**Open-source LLM Video Editor**

Combine Vision-Language Models with Autonomous Agents for intelligent video editing.

## Philosophy

Bring Your Own Model (BYOM). We don't lock you into one provider. Use OpenAI, Anthropic, Google, or run everything locally with Ollama.

## Quick Start

```bash
git clone https://github.com/yourusername/cineai.git
cd cineai
cp .env.example .env
# Add your API keys to .env
docker-compose up
```

Visit `http://localhost:3000`

## Example

```python
from cineai import Editor

editor = Editor()
result = editor.edit(
    video="interview.mp4",
    prompt="Make this more engaging, remove dead air, add B-roll"
)
```

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md)

## Features (Planned)

- [ ] Semantic video understanding (VLM)
- [ ] Autonomous editing agent
- [ ] Natural language interface
- [ ] BYOM support
- [ ] Iterative refinement
- [ ] Web UI + API

## Contributing

MIT License. Contributions welcome.
