import re
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import pymongo

from app.db.mongodb import get_chat_sessions_collection, get_chat_messages_collection

logger = logging.getLogger(__name__)


def generate_conversation_title(first_message: str) -> str:
    """
    Deterministically generates a concise, readable conversation title (max ~50 chars)
    from the first user query without invoking an LLM.
    """
    if not first_message or not first_message.strip():
        return "New Conversation"

    text = first_message.strip()

    # Strip language directives if present
    text = re.sub(r"^(?:Answer\s+in\s+(?:Telugu|Hindi|English):\s*)", "", text, flags=re.IGNORECASE)

    # Normalize excessive whitespace
    text = " ".join(text.split())

    # Common prefixes to clean for cleaner titles
    prefix_patterns = [
        r"^(?:what\s+are\s+the\s+timings\s+of\s+)",
        r"^(?:what\s+is\s+the\s+weather\s+(?:at|in|for)\s+)",
        r"^(?:what\s+will\s+a\s+visit\s+to\s+)",
        r"^(?:how\s+far\s+is\s+)",
        r"^(?:tell\s+me\s+about\s+)",
        r"^(?:can\s+you\s+tell\s+me\s+about\s+)",
        r"^(?:what\s+are\s+the\s+)",
        r"^(?:what\s+is\s+the\s+)",
        r"^(?:how\s+to\s+reach\s+)",
        r"^(?:plan\s+a\s+)",
    ]

    clean_text = text
    for pat in prefix_patterns:
        m = re.match(pat, clean_text, flags=re.IGNORECASE)
        if m:
            clean_text = clean_text[m.end():].strip()
            break

    # Strip trailing punctuation
    clean_text = clean_text.rstrip("?.! ")

    if not clean_text:
        clean_text = text.rstrip("?.! ")

    # Capitalize first letter
    if clean_text:
        clean_text = clean_text[0].upper() + clean_text[1:]

    # Truncate to 50 chars cleanly at word boundary
    if len(clean_text) > 50:
        truncated = clean_text[:47]
        last_space = truncated.rfind(" ")
        if last_space > 20:
            clean_text = truncated[:last_space] + "..."
        else:
            clean_text = truncated + "..."

    return clean_text or "New Conversation"


def save_user_message(
    user_id: str,
    session_id: str,
    content: str,
    db_name: Optional[str] = None
) -> None:
    """
    Saves a user message to chat_messages and ensures a chat_sessions document exists.
    """
    if not user_id or not session_id or not content:
        return

    now = datetime.now(timezone.utc)
    sessions_col = get_chat_sessions_collection(db_name)
    messages_col = get_chat_messages_collection(db_name)

    title = generate_conversation_title(content)

    # Upsert session document atomically
    sessions_col.update_one(
        {"user_id": user_id, "session_id": session_id},
        {
            "$setOnInsert": {
                "user_id": user_id,
                "session_id": session_id,
                "title": title,
                "created_at": now
            },
            "$set": {
                "updated_at": now
            }
        },
        upsert=True
    )

    # Insert user message
    messages_col.insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "role": "user",
        "content": content,
        "agent_name": None,
        "created_at": now
    })


def save_assistant_message(
    user_id: str,
    session_id: str,
    content: str,
    agent_name: Optional[str] = None,
    db_name: Optional[str] = None
) -> None:
    """
    Saves an assistant response to chat_messages and updates chat_sessions updated_at timestamp.
    """
    if not user_id or not session_id or not content:
        return

    now = datetime.now(timezone.utc)
    sessions_col = get_chat_sessions_collection(db_name)
    messages_col = get_chat_messages_collection(db_name)

    # Update session updated_at
    sessions_col.update_one(
        {"user_id": user_id, "session_id": session_id},
        {"$set": {"updated_at": now}}
    )

    # Insert assistant message
    messages_col.insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "role": "assistant",
        "content": content,
        "agent_name": agent_name,
        "created_at": now
    })


def get_user_sessions(
    user_id: str,
    limit: int = 50,
    db_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Returns all chat sessions belonging to user_id, sorted by updated_at descending.
    """
    if not user_id:
        return []

    sessions_col = get_chat_sessions_collection(db_name)
    cursor = sessions_col.find(
        {"user_id": user_id},
        {"_id": 0, "session_id": 1, "title": 1, "created_at": 1, "updated_at": 1}
    ).sort("updated_at", pymongo.DESCENDING).limit(limit)

    results = []
    for doc in cursor:
        created_at = doc.get("created_at")
        updated_at = doc.get("updated_at")
        results.append({
            "session_id": doc.get("session_id"),
            "title": doc.get("title") or "New Conversation",
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at or ""),
            "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else str(updated_at or "")
        })
    return results


def get_session_messages(
    user_id: str,
    session_id: str,
    db_name: Optional[str] = None
) -> Optional[List[Dict[str, Any]]]:
    """
    Returns all messages for a given (user_id, session_id) sorted by created_at ascending.
    Returns None if the session does not belong to the user or does not exist.
    """
    if not user_id or not session_id:
        return None

    sessions_col = get_chat_sessions_collection(db_name)
    session_exists = sessions_col.find_one({"user_id": user_id, "session_id": session_id})
    if not session_exists:
        return None

    messages_col = get_chat_messages_collection(db_name)
    cursor = messages_col.find(
        {"user_id": user_id, "session_id": session_id},
        {"_id": 0, "role": 1, "content": 1, "agent_name": 1, "created_at": 1}
    ).sort("created_at", pymongo.ASCENDING)

    messages = []
    for doc in cursor:
        created_at = doc.get("created_at")
        messages.append({
            "role": doc.get("role", "user"),
            "content": doc.get("content", ""),
            "agent_name": doc.get("agent_name"),
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at or "")
        })
    return messages


def delete_user_session(
    user_id: str,
    session_id: str,
    db_name: Optional[str] = None
) -> bool:
    """
    Deletes a conversation session and all its messages for the specified user_id.
    Returns True if found and deleted, False if not found.
    """
    if not user_id or not session_id:
        return False

    sessions_col = get_chat_sessions_collection(db_name)
    res = sessions_col.delete_one({"user_id": user_id, "session_id": session_id})
    if res.deleted_count == 0:
        return False

    messages_col = get_chat_messages_collection(db_name)
    messages_col.delete_many({"user_id": user_id, "session_id": session_id})
    return True
