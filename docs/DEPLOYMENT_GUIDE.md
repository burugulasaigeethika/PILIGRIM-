# PilgrimAI — Production Deployment Guide

## 1. Prerequisites & Environment Setup
- **Operating System**: Windows 10/11 or Linux (Ubuntu 22.04 LTS+)
- **Python**: Python 3.11.x (x64)
- **Ollama**: Local Ollama runtime (installed and listening on `http://127.0.0.1:11434`)
- **GPU/CPU**: Minimum 8 GB RAM (16 GB recommended). Dedicated NVIDIA GPU with 4GB+ VRAM recommended for < 5s generation latency.

---

## 2. Ollama Installation & Model Setup
1. Download and install Ollama from [ollama.com](https://ollama.com).
2. Set custom model storage if desired:
   ```powershell
   [System.Environment]::SetEnvironmentVariable('OLLAMA_MODELS', 'D:\Ollama\models', 'Machine')
   ```
3. Pull the certified production model:
   ```bash
   ollama pull qwen2.5:1.5b
   ```
4. Start Ollama:
   ```bash
   ollama serve
   ```

---

## 3. Python Virtual Environment & Dependencies
1. Create and activate a Python 3.11 virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## 4. On-Disk Local Indexes & Dataset
Ensure the following directories are present in the workspace root:
- 20 Temple Directories (e.g., `ahobilam/`, `badrachalam/`, `dharmapuri/`, `yadadri/`, etc.) with 417 source JSON files.
- `qdrant_db/` — Pre-indexed local Qdrant collection (1,578 parent contexts).
- `bm25_index/` — Pre-indexed local BM25 index (4,458 indexed documents).

---

## 5. Starting the Full-Stack Application
Start the FastAPI server (which hosts the REST API and the web UI):
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```
Access the application:
- **Web UI**: `http://127.0.0.1:8000/`
- **Interactive API Docs**: `http://127.0.0.1:8000/docs`
- **Health Endpoint**: `http://127.0.0.1:8000/health`

---

## 6. Health & Sanity Verification
Run the automated smoke test suite:
```bash
pytest tests/test_full_stack_smoke.py -v
```

---

## 7. Troubleshooting
- **Port 8000 in use**: Specify an alternate port via `--port 8080` and ensure CORS settings are intact.
- **Ollama Connection Refused**: Verify `ollama serve` is running on `http://127.0.0.1:11434`.
- **Qdrant Storage Lock**: Ensure only one active backend process accesses `qdrant_db/`.
