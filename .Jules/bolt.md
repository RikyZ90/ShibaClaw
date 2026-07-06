## 2025-02-12 - CLI Startup Time
**Learning:** `typer` and `pydantic` represent ~300ms of startup time for the CLI. Attempting to make them lazy-load requires major architectural refactoring (CLI registration relies heavily on module-level decorators). However, `rich` is eagerly imported in many files, causing an additional 30-50ms penalty.
**Action:** Replace module-level `rich` imports with local imports inside functions/commands, and wrap `Console()` in a `get_console()` singleton to defer instantiation.
