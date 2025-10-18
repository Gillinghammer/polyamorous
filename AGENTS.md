# Agent Guidelines for Poly TUI

## Scope
These instructions apply to the entire repository.

## Canonical References
- Follow the product requirements in `prd.md`.
- Consult implementation patterns in `docs/textual-guide.md`, `docs/polymarket-client-guide.md`, and `docs/grok-agentic-guide.md` before changing related components.

## General Coding Practices
- Target Python 3.11 compatibility with `textual>=0.40` APIs.
- Prefer dataclasses for domain models (markets, research sessions, trades).
- Use type hints throughout and keep functions pure where practical.
- Separate I/O (network, filesystem) from UI logic; expose service classes for data access and long-running tasks.
- Provide graceful fallbacks for missing optional dependencies or offline execution while keeping production pathways available.
- Favor dependency injection for services that need configuration (API keys, database paths).

### No-Fallback Rule (Project-wide)
- Fail fast when required dependencies or endpoints are unavailable.
- Do not include simulation, offline, or multi-endpoint fallbacks in production paths.
- Surface clear errors to the UI/logs and instruct the user to provide credentials/install deps.

## Testing & Tooling
- Ensure `python -m compileall poly` succeeds after changes.
- When adding async flows, provide unit-testable coroutine helpers separate from Textual widgets.

## Documentation & Comments
- Document public functions/classes with concise docstrings explaining responsibilities.
- Keep inline comments focused on intent rather than restating code.

## PR Expectations
- Summaries should emphasize user-facing behavior (e.g., "Add poll research view" rather than implementation details).
- Include testing commands executed and their results in the final response.
