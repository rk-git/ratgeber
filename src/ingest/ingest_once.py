"""
ingest.py - Ratgeber document ingestion pipeline

Reads Linbit documentation, chunks it, embeds it
and stores it in ChromaDB for RAG retrieval.

copyright (c) 2026 Always Up Networks. MIT License.
"""
from pathlib import Path
from typing import List

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
import spacy
from langdetect import detect
import logging
from enum import Enum

from spacy.language import Language
from typing import Final

from src.config import config

CHUNK_SIZE: Final[int] = 500
CHUNK_OVERLAP: Final[int] = 50

class LangType(Enum):
    UNSUPPORTED = 0
    ENGLISH = 1
    GERMAN = 2

SPACY_MODELS = {
    LangType.ENGLISH: "en_core_web_sm",
    LangType.GERMAN: "de_core_news_sm",
}

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DOCS_DIR = PROJECT_ROOT / "data" / "docs"
DATA_CHROMA_DIR = PROJECT_ROOT / "data" / "chroma_db"

def load_document(filename: Path) ->  List[Document]:
    if not filename.is_file():
        logging.error(f"Expected file, got something else: {filename}")
        raise FileNotFoundError(f"Not a file: {filename}")

    if filename.suffix == ".pdf":
        loader = PyPDFLoader(str(filename))
        return loader.load()
    elif filename.suffix == ".txt":
        loader = TextLoader(str(filename))
        return loader.load()
    elif filename.suffix == ".md":
        loader = TextLoader(str(filename))
        return loader.load()
    else:
        logging.error(f"Unsupported file type: {filename}")
        return []

def load_spacy_model(lang: LangType) -> Language:
    model_name = SPACY_MODELS.get(lang)
    if model_name is None:
        raise ValueError(f"Unsupported language: {lang}")

    return spacy.load(model_name)

def chunk_document(documents: List[Document]) -> List[Document]:
    output_chunks = []

    for doc in documents:
        lang = detect_language(doc.page_content, source=doc.metadata.get("source", "unknown"))
        if lang == LangType.UNSUPPORTED:
            logging.warning(f"Skipping document with unsupported language: {doc.metadata}")
            continue

        nlp = load_spacy_model(lang)
        spacy_doc = nlp(doc.page_content)

        buffer = []
        size = 0

        for sent in spacy_doc.sents:
            text = sent.text.strip()
            buffer.append(text)
            size += len(text)

            if size >= CHUNK_SIZE:
                output_chunks.append(
                    Document(
                        page_content=" ".join(buffer),
                        metadata=doc.metadata
                    )
                )
                buffer = []
                size = 0

        if buffer:
            output_chunks.append(
                Document(
                    page_content=" ".join(buffer),
                    metadata=doc.metadata
                )
            )

    logging.info(f"Split into {len(output_chunks)} chunks")
    return output_chunks

def detect_language(text: str, source: str = "unknown") -> LangType:
    try:
        lang = detect(text)
        if lang == "en":
            return LangType.ENGLISH
        elif lang == "de":
            return LangType.GERMAN
        else:
            logging.warning(f"Unsupported language detected: src = {source} {text[:10]}")
            return LangType.UNSUPPORTED

    except Exception as e:
        logging.warning(f"Exception due to Unsupported language detected: {e} , src = {source} {text[:10]}")
        return LangType.UNSUPPORTED


def ingest_file(filepath: str):
    file = Path(filepath)
    if not file.is_file():
        logging.error(f"Expected file, got something else: {filepath}")
        raise FileNotFoundError(f"Not a file: {filepath}")

    content = load_document(file)

    # Chunk the documents...
    output_chunks = chunk_document(content)


    # Store each chunk in ChromaDB with metadata
    for i, chunk in enumerate(output_chunks):
        # Embed each chunk using Sentence Transformer
        embedding = config.embedding_model.encode(chunk.page_content).tolist()
        config.collection.add(
            documents=[chunk.page_content],
            embeddings=[embedding],
            ids=[f"{file.name}_chunk_{i}"],
            metadatas=[chunk.metadata]
        )

    # Log progress
    logging.info(f"Ingested {len(output_chunks)} chunks")

def ingest_all(directory: str = str(DATA_DOCS_DIR)):
    root = Path(directory)
    if not root.is_dir():
        raise NotADirectoryError(
            f"Not a directory: {directory}"
        )

    logging.info(f"Scanning directory: {root}")

    files_found = 0
    for file in root.rglob("*"):
        if not file.is_file():
            continue
        if file.suffix.lower() not in SUPPORTED_EXTENSIONS:
            logging.info(f"Skipping unsupported file: {file}")
            continue
        try:
            logging.info(f"Ingesting file: {file}")
            ingest_file(str(file))
            files_found += 1
        except Exception as ex:
            logging.exception(
                f"Failed ingesting file: {file} : {ex}"
            )

    logging.info(
        f"Finished ingesting {files_found} files"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_all()