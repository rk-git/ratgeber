"""
chromadb.py - Ratgeber chromadb utilities

Implements utility functions specific to Ratgeber and ChromaDB

copyright (c) 2026 Always Up Networks. MIT License.
"""
from src.rag.retriever import retrieve


def retrieve_query_context(query:str) -> str:
    results = retrieve(query)
    context = "\n\n".join(results)
    return context
