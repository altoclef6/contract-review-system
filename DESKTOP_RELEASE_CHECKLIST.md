# Desktop release checklist

- [ ] Version and changelog are final.
- [ ] No `.env`, credentials, real contracts, or user data are staged.
- [ ] `pytest`, Ruff, Mypy, and the frontend production build pass.
- [ ] PyInstaller onedir health and fictional-document workflow pass.
- [ ] NSIS installer and portable ZIP are generated.
- [ ] Installer lifecycle smoke test reports `INSTALLER_SMOKE=PASS`.
- [ ] Backend has exactly one `127.0.0.1` listener on a random port.
- [ ] Normal app close leaves no backend process.
- [ ] Upgrade install preserves `%LOCALAPPDATA%\ContractReview`.
- [ ] Uninstall removes program files and preserves user data.
- [ ] SHA-256 values are recorded.
- [ ] Authenticode signature is applied, or unsigned/SmartScreen status is disclosed.
- [ ] A separate clean Windows 10/11 x64 user or VM completes manual acceptance.

Release automation is tag-gated with `desktop-v*`; ordinary Linux CI remains
unchanged.
