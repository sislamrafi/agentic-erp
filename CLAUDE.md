# NextERP — notes for AI agents

Read `README.md` first: it explains the architecture (resource registry → A2UI screens → agent tools → realtime SSE),
how to run it, the API, recipes for common changes, and known gotchas.

Hard rules:
- Never read, print, log or commit values in `backend/.env` (secrets). Variable names only; add new vars to `backend/.env.example`.
- Every data write must call `events.data_changed(...)` so all live surfaces refresh.
- Keep `CATALOG` in `backend/app/a2ui.py`, `frontend/src/components/a2ui/Renderer.tsx` and the `render_ui` tool description in sync.
- Resource shape lives only in `RESOURCES` (`backend/app/resources.py`); screens in `screens.py`; actions in `handle_action`.
- Run backend with `--timeout-graceful-shutdown 2` (SSE blocks reload otherwise). Demo login: sislamrafi333@gmail.com / Admin@123.
