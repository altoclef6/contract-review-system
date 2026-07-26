# Windows Desktop stage results

## Stage 1 - feasibility audit and ADR

- Date: 2026-07-26
- Baseline: `85d8fb6`
- Result: passed

### Changed files

- `docs/adr/0001-windows-desktop-lite.md`
- `docs/desktop/STAGE_RESULTS.md`

### Commands and observed results

- `git status --short --branch`: release-candidate worktree was clean.
- `python --version`: `Python 3.12.10`.
- `node --version`: `v24.18.0`.
- `pnpm --version`: `11.9.0`.
- `cargo --version`: command missing.
- `rustc --version`: command missing.
- `pyinstaller --version`: command missing.
- architecture searches confirmed centralized FastAPI application creation,
  database session setup, optional Redis, existing health endpoints, and a
  centralized Axios client.
- `.venv\Scripts\python.exe -m pytest tests/test_health.py
  tests/test_infrastructure.py -q`: `4 passed in 13.09s` (exit code 0).
- `.venv\Scripts\python.exe -m ruff check docs`: exit code 0; Ruff reported
  that the documentation tree contains no Python files.

The first test attempt with the global Python installation failed during
collection because `defusedxml` was missing. A worktree-local `.venv` was
created and `requirements.txt` plus `requirements-dev.txt` were installed;
the same gate then passed. No test was skipped.

### Decisions

See `docs/adr/0001-windows-desktop-lite.md`. The accepted design uses Tauri 2,
PyInstaller `onedir`, SQLite, loopback-only random-port communication, a
per-launch token, DPAPI, and `%LOCALAPPDATA%\ContractReview`.

## Stage 2 - backend desktop mode

- Date: 2026-07-26
- Result: passed

### Changed files

- `src/contract_review/core/config.py`
- `src/contract_review/core/middleware.py`
- `src/contract_review/main.py`
- `src/contract_review/services/local_task_executor.py`
- `src/contract_review/services/review_task_service.py`
- `src/contract_review/api/v1/endpoints/contracts.py`
- `src/contract_review/api/v1/endpoints/review_tasks.py`
- `tests/test_desktop_mode.py`

### Commands and observed results

- focused Ruff gate on the changed desktop runtime modules: all checks passed
  (exit code 0).
- focused strict Mypy gate on five desktop runtime source files: no issues found
  (exit code 0).
- `.venv\Scripts\python.exe -m pytest tests/test_desktop_mode.py
  tests/test_health.py tests/test_review_tasks.py -q`: `12 passed in 6.58s`
  (exit code 0).
- repository-wide Ruff was also attempted and reported 334 pre-existing
  formatting and FastAPI `B008` findings. The focused changed-file gate is
  clean; those unrelated baseline findings were not silently rewritten as part
  of this stage.

### Result

`APP_MODE=desktop` now requires a strong per-launch token, forbids Redis, protects
all non-health API calls with constant-time token comparison, and uses a bounded
event-loop-native executor instead of calling `asyncio.run()` inside FastAPI.
The executor is cancelled cleanly during application shutdown.

## Stage 3 - SQLite and local directories

- Date: 2026-07-26
- Result: passed

### Changed files

- `src/contract_review/core/config.py`
- `src/contract_review/database/session.py`
- `src/contract_review/main.py`
- `tests/test_desktop_mode.py`

### Commands and observed results

- SQLite schema probe using `Base.metadata.create_all()` against an in-memory
  database: all 13 mapped tables created (exit code 0).
- focused Ruff gate: all checks passed (exit code 0).
- focused strict Mypy gate: no issues found in 3 source files (exit code 0).
- `.venv\Scripts\python.exe -m pytest tests/test_desktop_mode.py
  tests/test_health.py tests/test_infrastructure.py tests/test_auth_flow.py -q`:
  `14 passed in 8.11s` (exit code 0).

### Result

Desktop mode derives every mutable path from `DESKTOP_DATA_DIR` or
`%LOCALAPPDATA%\ContractReview`, forces SQLite and database availability, creates
the required `database`, `uploads`, `reports`, `logs`, `config`, and `backups`
directories, and initializes the local schema. The Web/PostgreSQL configuration
path is unchanged.

## Stage 4 - PyInstaller onedir backend

- Date: 2026-07-26
- Result: passed

### Changed files

- `desktop/backend_entry.py`
- `desktop/contract-review-backend.spec`
- `scripts/build-desktop-backend.ps1`
- `tests/test_backend_entry.py`

### Commands and observed results

- installed `PyInstaller 6.21.0` into the worktree virtual environment.
- backend entry Ruff and strict Mypy gates passed.
- focused backend-entry/desktop tests: `7 passed in 4.94s`.
- `.\scripts\build-desktop-backend.ps1`: successful `onedir` build.
- first EXE startup failed because the initial spec did not collect
  `contract_review/web/static`; the spec was corrected and the backend rebuilt.
- final backend EXE SHA-256:
  `6CBFA6A5385D62C502852BB488EF0D0A7F0B6BF34DF9A78A0E71CE36CB1BF411`.
- real packaged-process smoke: readiness `ready`; listener
  `127.0.0.1:57100`; missing startup token returned 401; valid token returned
  200; shutdown left no backend process.
- real packaged workflow using `samples/generated/10_table_contract.docx`:
  registration and login succeeded, review returned 201 with 14 risks, and
  generated DOCX, JSON, Markdown, PDF, and XLSX exports. The process terminated
  completely after the workflow.

### Result

The standalone `onedir` backend runs without the development Python interpreter,
accepts the required four command-line arguments, binds only to loopback, creates
its SQLite/data layout, enforces the startup token, performs a deterministic
DOCX review, and exports every required report format.
