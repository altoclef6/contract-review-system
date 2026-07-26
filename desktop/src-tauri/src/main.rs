#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::{
    io::{Read, Write},
    net::{TcpListener, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};
use tauri::{Manager, State};
use uuid::Uuid;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct RuntimeConfig {
    api_origin: String,
    startup_token: String,
}

#[derive(Default)]
struct BackendState {
    child: Mutex<Option<Child>>,
    runtime: Mutex<Option<RuntimeConfig>>,
}

fn reserve_loopback_port() -> Result<u16, String> {
    let listener = TcpListener::bind(("127.0.0.1", 0)).map_err(|error| error.to_string())?;
    listener
        .local_addr()
        .map(|address| address.port())
        .map_err(|error| error.to_string())
}

fn backend_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    app.path()
        .resource_dir()
        .map(|path| {
            path.join("resources")
                .join("backend")
                .join("contract-review-backend.exe")
        })
        .map_err(|error| error.to_string())
}

fn ready(port: u16) -> bool {
    let Ok(mut stream) = TcpStream::connect_timeout(
        &format!("127.0.0.1:{port}")
            .parse()
            .expect("valid loopback address"),
        Duration::from_millis(500),
    ) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(1)));
    if stream
        .write_all(
            b"GET /api/v1/health/ready HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n",
        )
        .is_err()
    {
        return false;
    }
    let mut response = String::new();
    stream.read_to_string(&mut response).is_ok() && response.starts_with("HTTP/1.1 200")
}

fn stop_backend(state: &BackendState) {
    if let Some(mut child) = state
        .child
        .lock()
        .expect("backend child mutex poisoned")
        .take()
    {
        let _ = child.kill();
        let _ = child.wait();
    }
    state.runtime.lock().expect("runtime mutex poisoned").take();
}

fn start_backend(app: &tauri::AppHandle, state: &BackendState) -> Result<RuntimeConfig, String> {
    stop_backend(state);
    let port = reserve_loopback_port()?;
    let startup_token = format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple());
    let data_dir = app
        .path()
        .local_data_dir()
        .map_err(|error| error.to_string())?
        .join("ContractReview");
    let log_dir = data_dir.join("logs");
    std::fs::create_dir_all(&log_dir).map_err(|error| error.to_string())?;
    let executable = backend_path(app)?;
    if !executable.is_file() {
        return Err(format!(
            "Desktop backend is missing: {}",
            executable.display()
        ));
    }

    let mut command = Command::new(&executable);
    command
        .args([
            "--port",
            &port.to_string(),
            "--data-dir",
            &data_dir.to_string_lossy(),
            "--startup-token",
            &startup_token,
            "--log-dir",
            &log_dir.to_string_lossy(),
        ])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    command.creation_flags(0x08000000);
    let mut child = command.spawn().map_err(|error| error.to_string())?;

    let deadline = Instant::now() + Duration::from_secs(60);
    while Instant::now() < deadline {
        if ready(port) {
            let runtime = RuntimeConfig {
                api_origin: format!("http://127.0.0.1:{port}"),
                startup_token,
            };
            *state.child.lock().expect("backend child mutex poisoned") = Some(child);
            *state.runtime.lock().expect("runtime mutex poisoned") = Some(runtime.clone());
            return Ok(runtime);
        }
        if let Ok(Some(status)) = child.try_wait() {
            return Err(format!(
                "Desktop backend exited with {status}. Logs: {}",
                log_dir.display()
            ));
        }
        thread::sleep(Duration::from_millis(250));
    }
    let _ = child.kill();
    let _ = child.wait();
    Err(format!(
        "Desktop backend did not become ready. Logs: {}",
        log_dir.display()
    ))
}

#[tauri::command]
fn get_runtime_config(state: State<'_, BackendState>) -> Result<RuntimeConfig, String> {
    state
        .runtime
        .lock()
        .map_err(|_| "runtime mutex poisoned".to_string())?
        .clone()
        .ok_or_else(|| "Desktop backend is unavailable".to_string())
}

#[tauri::command]
fn restart_backend(
    app: tauri::AppHandle,
    state: State<'_, BackendState>,
) -> Result<RuntimeConfig, String> {
    start_backend(&app, state.inner())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .manage(BackendState::default())
        .invoke_handler(tauri::generate_handler![
            get_runtime_config,
            restart_backend
        ])
        .setup(|app| {
            let state = app.state::<BackendState>();
            start_backend(app.handle(), state.inner())
                .map(|_| ())
                .map_err(Into::into)
        })
        .build(tauri::generate_context!())
        .expect("failed to build ContractReviewDesktop")
        .run(|app, event| {
            if matches!(
                event,
                tauri::RunEvent::Exit | tauri::RunEvent::ExitRequested { .. }
            ) {
                let state = app.state::<BackendState>();
                stop_backend(state.inner());
            }
        });
}
