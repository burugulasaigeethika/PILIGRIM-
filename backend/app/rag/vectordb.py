import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from langchain_core.documents import Document

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, MatchAny

from app.rag.config import settings
from app.rag.embeddings import LocalEmbeddings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "temple_chunks"

class LocalQdrantManager:
    """
    Manages local, persistent on-disk Qdrant vector storage using qdrant-client.
    Zero cloud dependencies, zero API keys required.
    """

    def __init__(self, persist_dir: str = settings.QDRANT_DIR):
        self.persist_dir = persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)
        self._client: Optional[QdrantClient] = None
        self.parent_store_path = Path(self.persist_dir) / "parent_store.json"

    def get_client(self) -> QdrantClient:
        """Returns or initializes QdrantClient instance."""
        if self._client is None:
            self._client = QdrantClient(path=self.persist_dir)
        return self._client

    def close(self):
        """Closes Qdrant client connection if open."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def create_collection(
        self,
        child_chunks: List[Document],
        parent_store: Dict[str, str],
        embeddings: LocalEmbeddings
    ):
        """
        Creates Qdrant collection, embeds child chunks, stores points with full metadata payload,
        and saves parent_store map to local disk.
        """
        if not child_chunks:
            raise ValueError("Child chunk list is empty. Cannot build Qdrant vectorstore.")

        client = self.get_client()
        logger.info(f"Recreating Qdrant collection '{COLLECTION_NAME}' ({len(child_chunks)} chunks)...")

        sample_vec = embeddings.embed_query("test sample")
        vector_dim = len(sample_vec)

        client.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE)
        )

        texts = [chunk.page_content for chunk in child_chunks]
        logger.info(f"Computing embeddings for {len(texts)} chunks...")
        vectors = embeddings.embed_documents(texts)

        points = []
        for idx, (chunk, vec) in enumerate(zip(child_chunks, vectors)):
            payload = chunk.metadata.copy()
            payload["text"] = chunk.page_content

            points.append(PointStruct(
                id=idx,
                vector=vec,
                payload=payload
            ))

        batch_size = 100
        for i in range(0, len(points), batch_size):
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=points[i : i + batch_size]
            )

        logger.info(f"[OK] Upserted {len(points)} points into Qdrant collection '{COLLECTION_NAME}'.")

        with open(self.parent_store_path, "w", encoding="utf-8") as f:
            json.dump(parent_store, f, indent=2, ensure_ascii=False)
        logger.info(f"[OK] Parent store ({len(parent_store)} entries) saved to '{self.parent_store_path}'.")

    def search_candidates(
        self,
        query: str,
        embeddings: LocalEmbeddings,
        top_k: int = settings.CANDIDATE_POOL_TOP_K,
        filter_temple: Optional[str] = None
    ) -> List[Document]:
        """
        Searches Qdrant for top-K nearest neighbor child chunks matching query vector.
        Returns candidate LangChain Document instances with distance scores in metadata.
        """
        client = self.get_client()
        query_vec = embeddings.embed_query(query)

        query_filter = None
        if filter_temple:
            cands = list(dict.fromkeys([
                filter_temple,
                filter_temple.title(),
                filter_temple.lower(),
                filter_temple.upper(),
                filter_temple.capitalize()
            ]))
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="temple",
                        match=MatchAny(any=cands)
                    )
                ]
            )

        # Execute vector query using query_points (qdrant-client >= 1.7)
        if hasattr(client, "query_points"):
            response = client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vec,
                limit=top_k,
                query_filter=query_filter
            )
            search_results = response.points
        else:
            search_results = client.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_vec,
                limit=top_k,
                query_filter=query_filter
            )

        candidates = []
        for hit in search_results:
            payload = hit.payload.copy()
            text = payload.pop("text", "")
            meta = payload
            meta["score"] = float(hit.score)
            candidates.append(Document(page_content=text, metadata=meta))

        return candidates

    def load_parent_store(self) -> Dict[str, str]:
        """Loads parent_store dictionary from disk."""
        if not self.parent_store_path.exists():
            logger.warning(f"Parent store file '{self.parent_store_path}' not found.")
            return {}
        with open(self.parent_store_path, "r", encoding="utf-8") as f:
            return json.load(f)
