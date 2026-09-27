"""
PilgrimAI - Source Data & Protected Directory Integrity Checker
Verifies all 417 source temple JSON files and protected directories.
"""

import hashlib
from pathlib import Path

TEMPLE_FOLDERS = [
    "ahobilam", "badrachalam", "balkampet", "basara", "birla mandir",
    "chilkur", "dharmapuri", "edupayal", "jogulamba(new)", "kaleshvaram",
    "karmanghat", "medaram", "ramappa", "srisaila", "thousand pillar",
    "ttd", "ujjaini", "veera satyanarayana", "vemulavada", "yadadri"
]
BASELINE_HASH = "e816abe1f782b338ba3a80e2fd3b937fad9c535a32e03af871da93d81c4b15b3"

def verify():
    root = Path(r"D:\pligrim ai new")
    json_files = []
    for tf in TEMPLE_FOLDERS:
        folder = root / tf
        if folder.exists():
            json_files.extend(list(folder.glob("*.json")))
    
    json_files = sorted(json_files, key=lambda p: str(p))
    print(f"Total source JSON files found: {len(json_files)}")
    assert len(json_files) == 417, f"Expected 417 files, got {len(json_files)}"

    hasher = hashlib.sha256()
    for p in json_files:
        content = p.read_bytes()
        file_hash = hashlib.sha256(content).hexdigest()
        hasher.update(f"{p.name}:{file_hash}".encode("utf-8"))

    combined_hash = hasher.hexdigest()
    print(f"Calculated 417 Files Combined SHA-256: {combined_hash}")
    print(f"Baseline Combined SHA-256:           {BASELINE_HASH}")
    
    if combined_hash == BASELINE_HASH:
        print("\n>>> DATA INTEGRITY VERIFIED: 417/417 SOURCE JSON FILES UNCHANGED (100% MATCH) <<<")
    else:
        print("\n>>> WARNING: SHA-256 HASH MISMATCH <<<")

    # Check protected directories
    for d in ["qdrant_db", "bm25_index", "evaluation", "backend/app/rag"]:
        p = Path(r"D:\pligrim ai new") / d
        print(f"Protected directory '{d}' exists: {p.exists()}")

if __name__ == "__main__":
    verify()
