import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Generator, Tuple

from app.rag.config import settings
from app.rag.utils import format_temple_name

logger = logging.getLogger(__name__)

# Reserved directory names that are not temple data folders
RESERVED_DIRS = {
    "backend", "qdrant_db", "bm25_index", "faiss_index", "chroma",
    ".git", ".venv", "tests", "__pycache__", "node_modules", "scratch",
    "docs", "evaluation"
}

class TempleDatasetLoader:
    """Dynamically scans dataset directory and loads JSON files for all temples without hardcoding."""

    def __init__(self, dataset_dir: str = settings.DATASET_DIR):
        self.dataset_dir = Path(dataset_dir)

    def discover_temple_folders(self) -> List[Path]:
        """Scan dataset directory and return paths of non-empty temple directories."""
        target_dir = self.dataset_dir
        if not target_dir.exists() or not target_dir.is_dir():
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            if project_root.exists():
                logger.info(f"Dataset dir '{target_dir}' not found. Falling back to '{project_root}'.")
                target_dir = project_root
            else:
                logger.error(f"Dataset directory '{self.dataset_dir}' does not exist.")
                raise FileNotFoundError(f"Dataset directory '{self.dataset_dir}' not found.")

        self.resolved_dataset_dir = target_dir
        temple_folders = []
        for entry in target_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith(".") and entry.name.lower() not in RESERVED_DIRS:
                # Check if directory or its subdirectories contain at least one json file
                json_files = list(entry.glob("*.json")) + list(entry.rglob("*.json"))
                if json_files:
                    temple_folders.append(entry)

        return temple_folders

    def load_temple_files(self) -> Generator[Tuple[str, str, str, Any], None, None]:
        """
        Yields tuples of:
        (temple_name, file_name, relative_path, json_content)
        """
        temple_folders = self.discover_temple_folders()

        for folder in temple_folders:
            temple_raw_name = folder.name
            temple_name = format_temple_name(temple_raw_name)
            json_files = list(folder.rglob("*.json"))

            for json_path in json_files:
                file_name = json_path.name
                rel_path = str(json_path.relative_to(self.resolved_dataset_dir)).replace("\\", "/")

                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if data:  # Ensure content is non-empty
                        yield (temple_name, file_name, rel_path, data)
                    else:
                        logger.warning(f"Skipping empty JSON file: {rel_path}")

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON format in '{rel_path}': {e}. Skipping.")
                except Exception as e:
                    logger.error(f"Failed to read file '{rel_path}': {e}. Skipping.")
