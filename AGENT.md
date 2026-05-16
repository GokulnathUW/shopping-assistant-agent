# [AGENT.md](http://AGENT.md)

Rules for writing code in this project.

---

## Code Style

- Write simple code. Do not overcomplicate simple logic
- Use type hints on all function parameters and return types
- Write docstrings only on non-obvious functions — one line is enough
- Add inline comments on lines that aren't self-explanatory, not on obvious ones
- Do not add a descriptive comment block at the top of every file
- Do not create a function for simple logic that is only used once
- Use `logging` instead of `print()`
- Keep functions focused — one job per function

## Error Handling

- Wrap every external API call in try/except
- On failure, log the error and return an empty result — never crash the pipeline

## Data

- Use Pydantic models for data passed between agent nodes — no raw dicts
- All constants and env vars come from `config/settings.py` — never hardcode inline

## Dependencies

- Do not add new packages without asking first
- Use `uv add` not `pip install`

## Git

- Commit messages: `feat:`, `fix:`, `chore:`, `refactor:`, `test:` prefixes
- One concern per commit — do not bundle unrelated changes

