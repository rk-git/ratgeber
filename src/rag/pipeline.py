"""
pipeline.py - Ratgeber user query processor

Receives users NL query, vectorizes it, sends the query to
ChromaDB and returns the top (configured) 5 queries.

copyright (c) 2026 Always Up Networks. MIT License.
"""
from typing import List
import logging

from src.prompt.builder import build_ratgeber_prompt
from src.rag.retriever import retrieve
import ollama

def query_ollama(prompt: str) -> str:
    response = ollama.chat(
        model='gemma3',
        messages=[
            {
                'role': 'user',
                'content': prompt
            }
        ]
    )

    answer = response['message']['content']

    logging.info(
        f"Answer to query '{prompt}' is '{answer}'"
    )

    return answer


def pipeline(query:str) -> str:
    results = retrieve(query)
    context = "\n\n".join(results)
    prompt = build_ratgeber_prompt(context, query)
    logging.info(f"Prompt built: {prompt}")
    response = query_ollama(prompt)
    logging.info(f"Query {query} yielded response {response}")
    return response
