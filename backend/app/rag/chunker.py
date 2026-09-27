import uuid
from typing import List, Tuple, Dict
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app.rag.config import settings

class ParentChildChunker:
    """
    Splits parent documents into smaller child chunks for precise vector embedding and BM25 retrieval.
    Preserves parent_id link on every child chunk for context reconstruction.
    """

    def __init__(
        self,
        child_chunk_size: int = settings.CHILD_CHUNK_SIZE,
        child_chunk_overlap: int = settings.CHILD_CHUNK_OVERLAP
    ):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_chunk_size,
            chunk_overlap=child_chunk_overlap,
            separators=["\n---\n", "\n\n", "\n", " ", ""]
        )

    def create_parent_child_chunks(
        self, parent_docs: List[Document]
    ) -> Tuple[List[Document], Dict[str, str]]:
        """
        Takes parent Document instances and returns:
        1. List of child Document chunks (with parent_id, chunk_id, metadata attached)
        2. Parent Store dictionary mapping parent_id -> full_parent_content
        """
        child_chunks = []
        parent_store = {}

        for parent_doc in parent_docs:
            parent_id = parent_doc.metadata.get("parent_id") or f"parent_{uuid.uuid4().hex[:10]}"
            parent_doc.metadata["parent_id"] = parent_id
            parent_store[parent_id] = parent_doc.page_content

            # Split parent text into child chunks
            splits = self.text_splitter.split_documents([parent_doc])

            for idx, split in enumerate(splits):
                chunk_id = f"{parent_id}_child_{idx}"
                child_metadata = split.metadata.copy()
                child_metadata["chunk_id"] = chunk_id
                child_metadata["child_index"] = idx

                child_chunks.append(Document(
                    page_content=split.page_content,
                    metadata=child_metadata
                ))

        return child_chunks, parent_store
