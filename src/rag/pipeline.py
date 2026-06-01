"""
pipeline.py - Ratgeber user query processor

Receives users NL query, vectorizes it, sends the query to
ChromaDB and returns the top (configured) 5 queries.

copyright (c) 2026 Always Up Networks. MIT License.
"""
import logging
from typing import List
from enum import Enum
from src.prompt.builder import build_ratgeber_prompt
from src.rag.chromadb import retrieve_query_context
import ollama

from src.utils import utils


class AgentType(str, Enum):
    UNSUPPORTED = ""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

def query_ollama(messages: List[dict]) -> str:
    response = ollama.chat(
        #model='llama3.2:3b',
        model='mistral',
        messages=messages
    )
    answer = response['message']['content']
    logging.info(f"Ollama response: {answer}")
    return answer

def augment_context(messages: List[dict], agent: AgentType, msg: str) -> List[dict]:
    appendage = {'role': agent.value, 'content': msg}
    return messages + [appendage]

def pipeline(query: str, messages: list) -> tuple[str, list]:
    logging.info(f"Context: {messages}")

    context = retrieve_query_context(query)
    prompt_behavioral, prompt_query = build_ratgeber_prompt(context, query)
    logging.info(f"Prompts built: {prompt_behavioral}, prompt_user: {prompt_query}")

    messages = augment_context(messages, AgentType.SYSTEM, prompt_behavioral)
    messages = augment_context(messages, AgentType.USER, prompt_query)

    raw_response = query_ollama(messages)
    response = raw_response #utils.strip_markdown(raw_response)
    messages = augment_context(messages, AgentType.ASSISTANT, response)

    return response, messages
