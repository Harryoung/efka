# Repository Guidelines

## Project Structure & Module Organization
The `backend/` service hosts FastAPI endpoints (`api/`), Claude agent logic (`agents/`), domain services (`services/`), and shared helpers (`utils/`). Keep configuration in `backend/config/settings.py` and persist artifacts in `backend/storage/` or `logs/`. The React client lives in `frontend/`, with composable UI under `src/components/`, API hooks in `src/services/`, and build tooling via `vite.config.js`. Static knowledge assets are tracked under `knowledge_base/`, while `docs/`, `scripts/`, and `docker/` contain reference materials, automation, and deployment assets respectively.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` (within `backend/`): create and enter an isolated runtime.
- `pip install -r backend/requirements.txt`: install API, agent, and testing dependencies.
- `python backend/main.py`: launch the FastAPI service on `http://localhost:8000`.
- `cd frontend && npm install`: install UI dependencies.
- `npm run dev` (inside `frontend/`): start Vite with hot reload at `http://localhost:3000`.
- `npm run build`: produce production assets into `frontend/dist/`.
- `npm run lint`: run ESLint with the enforced rule set.

## Coding Style & Naming Conventions
Use 4-space indentation and PEP 8 conventions for Python modules; prefer descriptive module names like `*_service.py` and async handlers suffixed with `_async`. Keep business logic in `services/` rather than routes. Frontend code follows modern React (function components, hooks) with PascalCase components inside `components/` and camelCase utilities. Run `npm run lint` before opening a PR; configure any formatter (e.g., Black) via pre-commit if added later to avoid divergence.

## Testing Guidelines
Backend tests rely on `pytest` and `pytest-asyncio`; place files in `backend/tests/test_*.py` and stub external Claude calls with fixtures. Aim for coverage on service layers and API contracts before merging. Frontend testing is not wired yet—use React Testing Library when introducing tests and keep specs beside components as `Component.test.jsx`. Document new test commands in this guide when they are added.

## Commit & Pull Request Guidelines
Follow a Conventional Commit style (`feat:`, `fix:`, `chore:`, `docs:`) and keep messages in the imperative mood. Each PR should summarize scope, list backend/frontend touchpoints, note new environment variables, and include screenshots or console captures for UI changes. Link to planning issues in the PR body and ensure CI commands (`pytest`, `npm run lint`) succeed locally before requesting review.

## Security & Configuration Tips
Never commit `.env` or credentials; copy from `.env.example` and store secrets via your runtime manager. Validate that uploads respect `MAX_UPLOAD_SIZE` and sanitize knowledge-base file names before merging. Review `scripts/` and `docker/` updates for hard-coded endpoints or keys, and rotate the Claude API token if exposed.
