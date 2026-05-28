"""
config.py - Ratgeber system initialization

Initializes embedding and chromadb

copyright (c) 2026 Always Up Networks. MIT License.
"""
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).parent.parent.parent
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
chroma_client = chromadb.PersistentClient(path=str(PROJECT_ROOT / "data" / "chroma_db"))
collection = chroma_client.get_or_create_collection(name="linbit_docs")