import os
import sys
import json
import logging
from pathlib import Path

# Configure stdout encoding to UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path to enable smooth module imports
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.rag.config import settings
from app.rag.loader import TempleDatasetLoader
from app.rag.parser import JSONToDocumentParser
from app.rag.chunker import ParentChildChunker
from app.rag.embeddings import get_embeddings_model
from app.rag.vectordb import LocalQdrantManager
from app.rag.bm25 import LocalBM25Manager

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

def run_ingestion():
    """Main ingestion routine to scan dataset, parse JSON, create parent-child chunks, embed, and store in Qdrant & BM25."""
    print("==================================================")
    print("Starting 100% Local PilgrimAI Temple Dataset Ingestion")
    print("==================================================")
    print(f"Dataset Path      : {settings.DATASET_DIR}")
    print(f"Qdrant Storage    : {settings.QDRANT_DIR}")
    print(f"BM25 Storage      : {settings.BM25_DIR}")
    print(f"Embedding Model   : {settings.EMBEDDING_MODEL}")
    print("==================================================")

    # 1. Initialize Loader, Parser, Chunker
    loader = TempleDatasetLoader(dataset_dir=settings.DATASET_DIR)
    parser = JSONToDocumentParser()
    chunker = ParentChildChunker()

    temple_folders = loader.discover_temple_folders()
    if not temple_folders:
        print(f"[ERROR] No non-empty temple folders found in dataset directory: {settings.DATASET_DIR}")
        return

    all_parent_docs = []
    category_summary = {}

    for folder in temple_folders:
        temple_raw_name = folder.name
        temple_name = temple_raw_name.title()

        print(f"\nProcessing Temple: '{temple_name}'...")
        json_files = list(folder.rglob("*.json"))

        temple_parents = []
        for json_path in json_files:
            rel_path = str(json_path.relative_to(loader.resolved_dataset_dir)).replace("\\", "/")
            file_name = json_path.name

            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if data:
                    parents = parser.parse_to_parent_documents(temple_name, file_name, rel_path, data)
                    temple_parents.extend(parents)
                    for doc in parents:
                        cat = doc.metadata.get("category", "general")
                        category_summary[cat] = category_summary.get(cat, 0) + 1
            except Exception as e:
                print(f"  [WARNING] Failed to parse {rel_path}: {e}")

        print(f"  -> Generated {len(temple_parents)} parent document sections")
        all_parent_docs.extend(temple_parents)

    if not all_parent_docs:
        print("\n[ERROR] No parent documents created. Aborting ingestion.")
        return

    print("\n--------------------------------------------------")
    print(f"Total Discovered Temples : {len(temple_folders)}")
    print(f"Total Parent Sections    : {len(all_parent_docs)}")
    print("Discovered Categories:")
    for cat, count in sorted(category_summary.items()):
        print(f"  • {cat.title()}: {count} document section(s)")
    print("--------------------------------------------------")

    # 2. Generate Child Chunks & Parent Map
    print("\nGenerating Parent-Child Chunks...")
    child_chunks, parent_store = chunker.create_parent_child_chunks(all_parent_docs)
    print(f"[OK] Generated {len(child_chunks)} child chunks ({len(parent_store)} parent context entries).")

    # 3. Build Local Qdrant Vector Collection
    print(f"\nBuilding Local Qdrant Vector Collection at '{settings.QDRANT_DIR}'...")
    embeddings = get_embeddings_model()
    qdrant_manager = LocalQdrantManager(persist_dir=settings.QDRANT_DIR)
    qdrant_manager.create_collection(
        child_chunks=child_chunks,
        parent_store=parent_store,
        embeddings=embeddings
    )

    # 4. Build Local BM25 Keyword Index
    print(f"\nBuilding Local BM25 Keyword Index at '{settings.BM25_DIR}'...")
    bm25_manager = LocalBM25Manager(persist_dir=settings.BM25_DIR)
    bm25_manager.build_index(child_chunks=child_chunks)

    print("\n==================================================")
    print("[SUCCESS] Local Ingestion Complete!")
    print(f"Qdrant DB : {settings.QDRANT_DIR}")
    print(f"BM25 Index: {settings.BM25_DIR}")
    print("==================================================")

if __name__ == "__main__":
    run_ingestion()
