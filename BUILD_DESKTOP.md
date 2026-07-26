# Build ContractReviewDesktop

The reproducible Windows build entry point is:

```powershell
.\scripts\build-windows-desktop.ps1
```

Prerequisites, outputs, alternate target-drive configuration, and signing
status are documented in [docs/desktop/BUILD_WINDOWS.md](docs/desktop/BUILD_WINDOWS.md).

The build is fail-fast and runs backend tests, Ruff, Mypy, the Vue production
build, PyInstaller onedir packaging, Tauri release compilation, and NSIS.

Installer lifecycle smoke test:

```powershell
.\scripts\test-windows-desktop-installer.ps1 `
  -Installer .\dist\windows\ContractReviewSetup-x64.exe
```
