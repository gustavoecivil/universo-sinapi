use serde::{Deserialize, Serialize};
use std::io::{BufReader, Read};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use tauri::{AppHandle, Emitter};

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct EtlOptions {
    mode: String,
    year: Option<u32>,
    month: Option<u32>,
    formats: Vec<String>,
    supabase: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct EnvStatus {
    ok: bool,
    project_root: String,
    python_path: String,
    message: String,
}

fn project_root() -> Result<PathBuf, String> {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .map_err(|e| format!("Não foi possível resolver a raiz do projeto: {e}"))
}

fn python_executable(root: &Path) -> PathBuf {
    if cfg!(windows) {
        root.join(".venv").join("Scripts").join("python.exe")
    } else {
        root.join(".venv").join("bin").join("python")
    }
}

fn build_args(options: &EtlOptions) -> Result<Vec<String>, String> {
    let mut args = vec!["-u".to_string(), "main.py".to_string()];

    match options.mode.as_str() {
        "latest" => args.push("--latest".to_string()),
        "current" => args.push("--current".to_string()),
        "specific" => {
            let year = options
                .year
                .ok_or_else(|| "Informe o ano da referência.".to_string())?;
            let month = options
                .month
                .ok_or_else(|| "Informe o mês da referência.".to_string())?;
            if !(1..=12).contains(&month) {
                return Err("O mês deve estar entre 1 e 12.".to_string());
            }
            args.push("--year".to_string());
            args.push(year.to_string());
            args.push("--month".to_string());
            args.push(month.to_string());
        }
        other => return Err(format!("Modo inválido: {other}")),
    }

    if !options.formats.is_empty() {
        args.push("--formats".to_string());
        args.extend(options.formats.iter().cloned());
    }

    if options.supabase {
        args.push("--supabase".to_string());
    }

    Ok(args)
}

/// Emite linhas em tempo real, incluindo atualizações com `\r` (progresso).
fn stream_output(
    app: AppHandle,
    stream: impl Read + Send + 'static,
    stderr: bool,
) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        let mut reader = BufReader::new(stream);
        let mut buf = Vec::new();

        loop {
            let mut byte = [0u8; 1];
            match reader.read(&mut byte) {
                Ok(0) => break,
                Ok(_) => {
                    let b = byte[0];
                    if b == b'\n' || b == b'\r' {
                        if buf.is_empty() {
                            continue;
                        }
                        let line = String::from_utf8_lossy(&buf).trim_end().to_string();
                        buf.clear();
                        if line.is_empty() {
                            continue;
                        }
                        let payload = if stderr {
                            format!("[stderr] {line}")
                        } else {
                            line
                        };
                        let _ = app.emit("etl-log", payload);
                    } else {
                        buf.push(b);
                    }
                }
                Err(_) => break,
            }
        }

        if !buf.is_empty() {
            let line = String::from_utf8_lossy(&buf).trim_end().to_string();
            if !line.is_empty() {
                let payload = if stderr {
                    format!("[stderr] {line}")
                } else {
                    line
                };
                let _ = app.emit("etl-log", payload);
            }
        }
    })
}

#[tauri::command]
fn check_env() -> Result<EnvStatus, String> {
    let root = project_root()?;
    let python = python_executable(&root);
    let main_py = root.join("main.py");

    if !python.exists() {
        return Ok(EnvStatus {
            ok: false,
            project_root: root.display().to_string(),
            python_path: python.display().to_string(),
            message: "Ambiente .venv não encontrado. Crie com: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt".to_string(),
        });
    }

    if !main_py.exists() {
        return Ok(EnvStatus {
            ok: false,
            project_root: root.display().to_string(),
            python_path: python.display().to_string(),
            message: "main.py não encontrado na raiz do repositório.".to_string(),
        });
    }

    Ok(EnvStatus {
        ok: true,
        project_root: root.display().to_string(),
        python_path: python.display().to_string(),
        message: "Ambiente Python pronto.".to_string(),
    })
}

#[tauri::command]
fn run_etl(app: AppHandle, options: EtlOptions) -> Result<(), String> {
    let root = project_root()?;
    let python = python_executable(&root);

    if !python.exists() {
        return Err(format!(
            "Python do .venv não encontrado em {}",
            python.display()
        ));
    }

    let args = build_args(&options)?;

    // Retorna imediatamente; o processo roda em background e emite eventos.
    thread::spawn(move || {
        let _ = app.emit(
            "etl-log",
            format!("$ {} {}", python.display(), args.join(" ")),
        );

        let child = Command::new(&python)
            .args(&args)
            .current_dir(&root)
            .env("PYTHONUNBUFFERED", "1")
            .env("PYTHONIOENCODING", "utf-8")
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn();

        let mut child = match child {
            Ok(c) => c,
            Err(e) => {
                let _ = app.emit("etl-log", format!("Falha ao iniciar o ETL: {e}"));
                let _ = app.emit(
                    "etl-finished",
                    serde_json::json!({ "code": -1, "success": false }),
                );
                return;
            }
        };

        let mut handles = Vec::new();

        if let Some(stdout) = child.stdout.take() {
            handles.push(stream_output(app.clone(), stdout, false));
        }
        if let Some(stderr) = child.stderr.take() {
            handles.push(stream_output(app.clone(), stderr, true));
        }

        let code = match child.wait() {
            Ok(status) => status.code().unwrap_or(-1),
            Err(e) => {
                let _ = app.emit("etl-log", format!("Falha ao aguardar o processo: {e}"));
                -1
            }
        };

        for handle in handles {
            let _ = handle.join();
        }

        let success = code == 0;
        let _ = app.emit(
            "etl-finished",
            serde_json::json!({ "code": code, "success": success }),
        );
    });

    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![check_env, run_etl])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
