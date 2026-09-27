import os
import re
import pickle
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from langchain_core.documents import Document

from rank_bm25 import BM25Okapi
from app.rag.config import settings

logger = logging.getLogger(__name__)

def tokenize_text(text: str) -> List[str]:
    """Tokenize input text into lowercase alphanumeric terms for BM25 indexing."""
    if not text:
        return []
    return re.findall(r'\w+', text.lower())

class LocalBM25Manager:
    """
    Manages local BM25 keyword search indexer and persistence.
    Catches exact terms like phone numbers, temple names, seva titles, and timings.
    """

    def __init__(self, persist_dir: str = settings.BM25_DIR):
        self.persist_dir = persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)
        self.store_path = Path(self.persist_dir) / "bm25_store.pkl"
        self.bm25: BM25Okapi = None
        self.documents: List[Document] = []

    def build_index(self, child_chunks: List[Document]):
        """
        Tokenizes child chunks, builds BM25 index, and persists store locally to disk.
        """
        if not child_chunks:
            raise ValueError("Child chunk list is empty. Cannot build BM25 index.")

        logger.info(f"Building local BM25 index for {len(child_chunks)} chunks...")
        tokenized_corpus = [
            tokenize_text(doc.page_content)
            for doc in child_chunks
        ]

        self.bm25 = BM25Okapi(tokenized_corpus)
        self.documents = child_chunks

        store_data = {
            "tokenized_corpus": tokenized_corpus,
            "documents": self.documents
        }

        with open(self.store_path, "wb") as f:
            pickle.dump(store_data, f)
        logger.info(f"[OK] BM25 index saved to '{self.store_path}'.")

    def load_index(self):
        """Loads BM25 index and document store from disk."""
        if not self.store_path.exists():
            raise FileNotFoundError(f"BM25 store file '{self.store_path}' does not exist. Please run ingestion first.")

        with open(self.store_path, "rb") as f:
            store_data = pickle.load(f)

        tokenized_corpus = store_data["tokenized_corpus"]
        self.documents = store_data["documents"]
        self.bm25 = BM25Okapi(tokenized_corpus)
        logger.info(f"[OK] Loaded local BM25 index ({len(self.documents)} documents) from '{self.store_path}'.")

    def search_candidates(
        self,
        query: str,
        top_k: int = settings.CANDIDATE_POOL_TOP_K
    ) -> List[Document]:
        """
        Performs BM25 keyword search for query and returns top-K ranked documents.
        """
        if self.bm25 is None or not self.documents:
            self.load_index()

        tokenized_query = tokenize_text(query)
        if not tokenized_query:
            return []

        scores = self.bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        candidates = []
        for idx in top_indices:
            score = float(scores[idx])
            if score <= 0:
                continue
            orig_doc = self.documents[idx]
            meta = orig_doc.metadata.copy()
            meta["bm25_score"] = score
            candidates.append(Document(page_content=orig_doc.page_content, metadata=meta))

        return candidates
