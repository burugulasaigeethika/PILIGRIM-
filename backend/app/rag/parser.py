import json
import uuid
from typing import List, Dict, Any, Union
from langchain_core.documents import Document
from app.rag.utils import sanitize_json_value
from app.rag.config import settings

class JSONToDocumentParser:
    """
    Structure-aware parser converting temple JSON structures into Parent Documents.
    Preserves hierarchical key-value context without loss of tabular meaning.
    Generates dynamic parent_id metadata for parent-child retrieval.
    """

    def __init__(self):
        pass

    def _format_dict(self, data: Dict[str, Any], indent_level: int = 0) -> str:
        """Recursively formats a JSON object into clean key-value text."""
        lines = []
        indent = "  " * indent_level

        for key, val in data.items():
            if val is None or val == "" or val == []:
                continue

            formatted_key = key.replace("_", " ").title()

            if isinstance(val, dict):
                lines.append(f"\n{indent}{formatted_key}:")
                lines.append(self._format_dict(val, indent_level + 1))

            elif isinstance(val, list):
                lines.append(f"\n{indent}{formatted_key}:")
                lines.append(self._format_list(val, indent_level + 1))

            else:
                clean_val = sanitize_json_value(val)
                lines.append(f"{indent}{formatted_key}: {clean_val}")

        return "\n".join(lines)

    def _format_list(self, items: List[Any], indent_level: int = 0) -> str:
        """Formats a JSON list into clean text."""
        lines = []
        indent = "  " * indent_level

        for item in items:
            if isinstance(item, dict):
                lines.append(self._format_dict(item, indent_level + 1))
                lines.append("---")
            elif isinstance(item, list):
                lines.append(self._format_list(item, indent_level + 1))
            else:
                clean_val = sanitize_json_value(item)
                if clean_val:
                    lines.append(f"{indent}- {clean_val}")

        return "\n".join(lines)

    def parse_to_parent_documents(
        self, temple_name: str, file_name: str, rel_path: str, json_data: Any
    ) -> List[Document]:
        """
        Converts loaded JSON data into parent LangChain Document instances.
        Dynamic category discovery is performed from top-level keys or filename.
        Assigns a unique parent_id to each Document.
        """
        fallback_category = file_name.replace(".json", "").lower()
        documents = []
        clean_temple = temple_name.lower().replace(" ", "_")

        if isinstance(json_data, dict):
            top_keys = list(json_data.keys())
            complex_sections = [
                k for k in top_keys
                if isinstance(json_data[k], (dict, list)) and len(json_data[k]) > 0
            ]

            if len(complex_sections) >= 1 and fallback_category not in complex_sections:
                # Multi-category JSON document
                for section_key in top_keys:
                    section_data = json_data[section_key]
                    if not section_data:
                        continue

                    cat_name = section_key.lower().replace("_", " ")
                    parent_id = f"parent_{clean_temple}_{section_key.lower()}_{uuid.uuid4().hex[:8]}"

                    metadata = {
                        "temple": temple_name,
                        "category": cat_name,
                        "source_file": file_name,
                        "path": rel_path,
                        "parent_id": parent_id
                    }
                    header = f"Temple: {temple_name}\nCategory: {cat_name.title()}\nFile: {file_name}\n\n"

                    if isinstance(section_data, dict):
                        body_text = self._format_dict(section_data)
                    elif isinstance(section_data, list):
                        body_text = self._format_list(section_data)
                    else:
                        body_text = f"{cat_name.title()}: {sanitize_json_value(section_data)}"

                    full_text = header + body_text
                    documents.append(Document(page_content=full_text, metadata=metadata))
            else:
                # Single category JSON document
                parent_id = f"parent_{clean_temple}_{fallback_category}_{uuid.uuid4().hex[:8]}"
                metadata = {
                    "temple": temple_name,
                    "category": fallback_category,
                    "source_file": file_name,
                    "path": rel_path,
                    "parent_id": parent_id
                }
                header = f"Temple: {temple_name}\nCategory: {fallback_category.title()}\nFile: {file_name}\n\n"
                body_text = self._format_dict(json_data)
                full_text = header + body_text
                documents.append(Document(page_content=full_text, metadata=metadata))

        elif isinstance(json_data, list):
            clean_category = fallback_category.lower()
            is_list_file = (
                file_name.lower() in settings.LIST_BASED_FILES
                or f"{clean_category}.json" in settings.LIST_BASED_FILES
            )

            if is_list_file and len(json_data) > 0:
                # Unified Complete List Parent Document
                parent_id = f"parent_{clean_temple}_{clean_category}_complete"
                header = f"Temple: {temple_name}\nCategory: {fallback_category.title()}\nFile: {file_name}\n\n"
                
                items_formatted = []
                for idx, item in enumerate(json_data):
                    if isinstance(item, dict):
                        items_formatted.append(self._format_dict(item))
                    else:
                        items_formatted.append(f"- {sanitize_json_value(item)}")
                
                full_body = "\n\n---\n\n".join(items_formatted)
                full_text = header + full_body
                metadata = {
                    "temple": temple_name,
                    "category": fallback_category,
                    "source_file": file_name,
                    "path": rel_path,
                    "parent_id": parent_id,
                    "is_complete_list": True,
                    "item_count": len(json_data)
                }
                documents.append(Document(page_content=full_text, metadata=metadata))

            elif len(json_data) > 0 and isinstance(json_data[0], dict):
                # Independent item parent documents (e.g., individual FAQ pairs)
                for idx, item in enumerate(json_data):
                    item_parent_id = f"parent_{clean_temple}_{clean_category}_{idx}_{uuid.uuid4().hex[:6]}"
                    item_text = self._format_dict(item)
                    doc_content = f"Temple: {temple_name}\nCategory: {fallback_category.title()}\nFile: {file_name}\n\n{item_text}"
                    item_metadata = {
                        "temple": temple_name,
                        "category": fallback_category,
                        "source_file": file_name,
                        "path": rel_path,
                        "parent_id": item_parent_id,
                        "item_index": idx
                    }
                    documents.append(Document(doc_content, metadata=item_metadata))
            else:
                parent_id = f"parent_{clean_temple}_{clean_category}_{uuid.uuid4().hex[:8]}"
                header = f"Temple: {temple_name}\nCategory: {fallback_category.title()}\nFile: {file_name}\n\n"
                list_text = self._format_list(json_data)
                full_text = header + list_text
                metadata = {
                    "temple": temple_name,
                    "category": fallback_category,
                    "source_file": file_name,
                    "path": rel_path,
                    "parent_id": parent_id
                }
                documents.append(Document(page_content=full_text, metadata=metadata))

        return documents
