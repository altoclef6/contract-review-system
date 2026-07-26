from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ContractReviewDesktop backend")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--startup-token", required=True)
    parser.add_argument("--log-dir", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if len(args.startup_token) < 32:
        parser.error("--startup-token must contain at least 32 characters")
    return args


def configure_environment(args: argparse.Namespace) -> None:
    data_dir = args.data_dir.expanduser().resolve()
    log_dir = args.log_dir.expanduser().resolve()
    if not log_dir.is_relative_to(data_dir):
        raise SystemExit("--log-dir must be located below --data-dir")
    data_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        {
            "APP_MODE": "desktop",
            "ENVIRONMENT": "local",
            "DESKTOP_DATA_DIR": str(data_dir),
            "DESKTOP_STARTUP_TOKEN": args.startup_token,
            "REDIS_ENABLED": "false",
            "ENABLE_LLM": "false",
            "JWT_SECRET_KEY": secrets.token_urlsafe(48),
            "BOOTSTRAP_ADMIN_PASSWORD": secrets.token_urlsafe(24),
            "MODEL_CREDENTIAL_ENCRYPTION_KEY": secrets.token_urlsafe(48),
            "TRUSTED_HOSTS": "127.0.0.1,localhost",
            "ALLOWED_ORIGINS": "tauri://localhost,http://tauri.localhost",
        }
    )


def main() -> int:
    args = parse_args()
    configure_environment(args)
    import uvicorn

    from contract_review.main import create_app

    uvicorn.run(
        create_app(),
        host="127.0.0.1",
        port=args.port,
        log_level="info",
        access_log=False,
        proxy_headers=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

