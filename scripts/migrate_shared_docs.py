#!/usr/bin/env python3
import os
import sys
import shutil

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.constants import DATA_DIR, SHARED_DIR
from src.chroma_client import get_chroma_client

def migrate():
    print(f"Migrating files from {SHARED_DIR}...")
    if not os.path.isdir(SHARED_DIR):
        print("SHARED_DIR not found. Nothing to migrate.")
        return

    try:
        client = get_chroma_client()
        collection = client.get_collection('personal_documents')
        docs = collection.get(include=['metadatas'])
    except Exception as e:
        print(f"Failed to connect to ChromaDB: {e}")
        return

    file_owners = {}
    for meta in docs['metadatas']:
        source = meta.get('source')
        owner = meta.get('owner')
        if source and owner and source.startswith(SHARED_DIR):
            file_owners[source] = owner

    if not file_owners:
        print("No files in SHARED_DIR with an owner metadata found in ChromaDB.")
        return

    moved_count = 0
    for source, owner in file_owners.items():
        if os.path.exists(source):
            target_dir = os.path.join(DATA_DIR, "users", owner, "personal_docs")
            os.makedirs(target_dir, exist_ok=True)
            target = os.path.join(target_dir, os.path.basename(source))
            if not os.path.exists(target):
                shutil.copy2(source, target)
                print(f"Moved {os.path.basename(source)} to {owner}'s personal_docs.")
                moved_count += 1
            else:
                print(f"File {os.path.basename(source)} already exists in {owner}'s personal_docs. Skipping.")

    print(f"Migration complete! Moved {moved_count} files.")

if __name__ == "__main__":
    migrate()
