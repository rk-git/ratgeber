"""
retriever.py - Ratgeber results retriever

Vectorizes NLP query with language context into vectors,
queries chromaDB and returns the top DEFAULT_RESULT_COUNT
results.

copyright (c) 2026 Always Up Networks. MIT License.
"""

from typing import List, Final

from src.config import config

DEFAULT_RESULT_COUNT: Final[int] = 10

def retrieve(query: str, n_results: int = DEFAULT_RESULT_COUNT) -> List[str]:
    query_vector = config.embedding_model.encode(query).tolist()
    results = config.collection.query(
        query_embeddings=[query_vector],
        n_results=n_results
    )

    return  results['documents'][0]

