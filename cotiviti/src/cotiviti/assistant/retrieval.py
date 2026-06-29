"""ChromaDB schema vector store — retrieves the columns most relevant to a question.

Persists one embedding per column description (Chroma's default local MiniLM model,
no external embedding API). Built once; reused across reruns.
"""
import chromadb
import streamlit as st
from chromadb.utils import embedding_functions

from . import config
from .schema import COLUMN_DOCS


@st.cache_resource(show_spinner="Indexing schema embeddings…")
def get_schema_collection():
    """Return a Chroma collection of column-description embeddings, seeding once."""
    client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))
    ef = embedding_functions.DefaultEmbeddingFunction()
    collection = client.get_or_create_collection(
        name=config.SCHEMA_COLLECTION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    if collection.count() == 0:
        collection.add(
            ids=list(COLUMN_DOCS.keys()),
            documents=[f"{col}: {desc}" for col, desc in COLUMN_DOCS.items()],
        )
    return collection


def retrieve_relevant_columns(question: str, k: int = config.TOP_K_COLUMNS) -> list[str]:
    """Return the ``k`` column names most semantically relevant to the question.

    Top-k (not a hard similarity cutoff): even strong column matches score well
    below 0.9, so a strict threshold would drop relevant columns. Falls back to
    all columns if retrieval fails for any reason.
    """
    try:
        collection = get_schema_collection()
        res = collection.query(query_texts=[question], n_results=min(k, len(COLUMN_DOCS)))
        return res["ids"][0]
    except Exception:
        return list(COLUMN_DOCS.keys())