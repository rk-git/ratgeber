"""
config.py - Ratgeber system initialization

Initializes embedding and chromadb

copyright (c) 2026 Always Up Networks. MIT License.
"""

import chromadb
from sentence_transformers import SentenceTransformer

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
chroma_client = chromadb.PersistentClient(path="../data/chroma_db")
collection = chroma_client.get_or_create_collection(name="linbit_docs")