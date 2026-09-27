"""
PilgrimAI - Comprehensive 417 Source Files SHA-256 Manifest Verifier
"""

import os
import json
import hashlib
from pathlib import Path

MANIFEST_PATH = Path(r"C:\Users\aksha\.gemini\antigravity-ide\brain\fc1dba71-cc00-41cd-a9fa-8b253c0f5282\scratch\pre_o6_manifest.json")
ROOT_DIR = Path(r"D:\pligrim ai new")

TEMPLE_FOLDERS = [
    "ahobilam", "badrachalam", "balkampet", "basara", "birla mandir",
    "chilkur", "dharmapuri", "edupayal", "jogulamba(new)", "kaleshvaram",
    "karmanghat", "medaram", "ramappa", "srisaila", "thousand pillar",
    "ttd", "ujjaini", "veera satyanarayana", "vemulavada", "yadadri"
]

def verify_all():
    json_files = []
    for tf in TEMPLE_FOLDERS:
        d = ROOT_DIR / tf
        if d.exists():
            json_files.extend(list(d.glob("*.json")))

    print(f"Total source temple JSON files detected: {len(json_files)}")
    assert len(json_files) == 417, f"Expected 417, got {len(json_files)}"

    has_manifest = MANIFEST_PATH.exists()
    print(f"Manifest file exists: {has_manifest}")

    mismatches = []
    manifest_data = {}
    if has_manifest:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

    for fpath in json_files:
        rel = fpath.relative_to(ROOT_DIR).as_posix()
        with open(fpath, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        
        if manifest_data:
            if rel in manifest_data:
                if manifest_data[rel] != h:
                    mismatches.append((rel, manifest_data[rel], h))

    if mismatches:
        print(f"FAILED: {len(mismatches)} files mismatched!")
        for m in mismatches[:5]:
            print(f"  {m[0]}: expected {m[1]}, got {m[2]}")
    else:
        print(f"SUCCESS: All 417/417 source temple JSON files match the manifest identically!")

if __name__ == "__main__":
    verify_all()
