# ADR 0001: Windows Desktop Lite architecture

- Status: Accepted
- Date: 2026-07-26
- Baseline: `85d8fb6` (`agent/enterprise-release-candidate-20260716`)
- Target: Windows 10/11 x64

## Context

The existing product is a FastAPI backend plus a Vue 3/TypeScript frontend. Its
production deployment assumes PostgreSQL, Redis, Celery, and Docker, while the
desktop edition must be installable without those runtimes. The desktop work
must preserve the Web/Docker deployment and reuse the existing parsing, rule
engine, authentication, authorization, upload validation, and report services.

The repository already provides useful seams:

- `create_app()` builds the FastAPI application without starting a server.
- database access is centralized in `database/session.py`.
- Redis is optional and the cache service already has a local fallback.
- review orchestration is centralized in `ReviewTaskService`.
- liveness and readiness endpoints already exist.
- the Vue client centralizes HTTP configuration in `frontend/src/api.ts`.

The audit also found gaps that must be closed before packaging:

- configuration has no explicit desktop mode and defaults to repository-relative
  data paths;
- synchronous fallback calls `asyncio.run()` and is unsafe from an active
  FastAPI event loop;
- no startup-token middleware protects the loopback API;
- SQLite engine options and schema migration startup are not defined;
- model credentials are file-encrypted rather than stored through Windows
  credential protection;
- the frontend assumes a same-origin `/api/v1` endpoint;
- no PyInstaller, Tauri, NSIS, or Windows CI definitions exist;
- Rust/Cargo and PyInstaller were not installed on the audit machine.

## Decision

Create a separate `desktop/` Tauri 2 application and keep all business logic in
`src/contract_review`. The Vue source remains in `frontend/`; desktop-specific
bootstrap code will only inject runtime connection information and expose a
small recovery surface.

The Tauri process will:

1. enforce a single application instance;
2. create `%LOCALAPPDATA%\ContractReview\` and its data subdirectories;
3. reserve a random loopback port and generate a cryptographically random
   startup token;
4. launch a fixed, bundled PyInstaller `onedir` sidecar with explicit
   `--port`, `--data-dir`, `--log-dir`, and `--startup-token` arguments;
5. wait for `/api/v1/health/ready`, then inject the loopback origin and token
   into the WebView;
6. terminate the sidecar when the application exits.

The backend desktop mode will be explicit (`APP_MODE=desktop`) and will:

- accept only `127.0.0.1` binding from its entry point;
- use SQLite under the supplied data directory;
- disable Redis and Celery and run review work in a bounded local executor;
- require the startup token on API routes while allowing liveness/readiness
  probes;
- create and migrate the local database before becoming ready;
- write uploads, reports, configuration, backups, and redacted logs only below
  the supplied data directory.

Model secrets will use Windows DPAPI, scoped to the current user. Configuration
records and backups will contain only a credential identifier and masked value.
The API will never return the plaintext key.

PyInstaller will use `onedir`. Tauri NSIS will install per-user and bundle that
directory as a fixed sidecar resource. `onefile` is explicitly deferred because
startup extraction and antivirus false positives reduce reliability.

## Security boundaries

- The backend binds only to loopback and rejects missing/invalid startup tokens.
- The frontend cannot choose an executable or arbitrary command.
- Tauri capabilities expose only fixed application commands.
- Upload extension, MIME, magic-byte, size, and DOCX ZIP checks remain enabled.
- No `.env`, real contract, API key, test key, database, or runtime log may be
  included in build artifacts.
- Logs redact authorization headers, passwords, tokens, model keys, and document
  bodies.
- Uninstall preserves `%LOCALAPPDATA%\ContractReview\` by default.

## Lite feature boundary

Text PDFs and DOCX are supported. Scanned PDFs, image contracts, and legacy
`.doc` files fail explicitly with:

> 桌面 Lite 版暂不支持该文档的本地解析，请转换为文本型 PDF 或 DOCX。

LibreOffice, Tesseract, Redis, Celery, PostgreSQL, LAN collaboration, and cloud
sync are not bundled in the first desktop release.

## Delivery stages and gates

1. Architecture audit and this ADR.
2. Desktop runtime mode, loopback/token enforcement, local executor.
3. SQLite, AppData layout, migration, backup/restore, DPAPI credentials.
4. PyInstaller `onedir` and real backend smoke workflow.
5. Tauri sidecar lifecycle and frontend runtime injection.
6. NSIS installer and portable archive.
7. Windows install/upgrade/uninstall automation.
8. Windows CI, build guide, release checklist, hashes.

Each stage requires its focused tests, Ruff, Mypy where applicable, a recorded
result, and an independent commit. A failed gate blocks the next stage.

## Consequences

The Web/Docker mode remains unchanged and continues using its existing
PostgreSQL/Redis/Celery configuration. Desktop adds Windows-specific code only at
the credential, process lifecycle, and installer boundaries. The main technical
risk is SQL dialect compatibility in existing migrations; it will be resolved
and tested before PyInstaller work begins.

