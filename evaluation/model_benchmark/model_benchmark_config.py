from pathlib import Path

MODEL_A = "qwen2.5:1.5b"
MODEL_B = "qwen2.5:7b"

BENCHMARK_DIR = Path(__file__).resolve().parent
BENCHMARK_DATASET_FILE = BENCHMARK_DIR / "benchmark_dataset.json"
MODEL_RESULTS_FILE = BENCHMARK_DIR / "model_results.json"
MODEL_COMPARISON_FILE = BENCHMARK_DIR / "model_comparison.json"
MODEL_COMPARISON_REPORT = BENCHMARK_DIR / "model_comparison_report.md"

# Evaluation parameters
OLLAMA_TIMEOUT_SECONDS = 180
NUM_BENCHMARK_QUESTIONS = 300
