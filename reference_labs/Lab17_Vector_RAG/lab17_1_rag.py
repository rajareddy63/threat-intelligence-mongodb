"""Threat-intelligence RAG demo with MongoDB Atlas vector search and memory."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from dotenv import load_dotenv
from pymongo import MongoClient


load_dotenv(Path(__file__).with_name(".env"), override=False)

DATABASE_NAME = os.getenv("MONGODB_DATABASE", "rag_demo")
DOCUMENT_COLLECTION = "documents"
CONVERSATION_COLLECTION = "conversations"
VECTOR_INDEX_NAME = os.getenv("RAG_VECTOR_INDEX", "rag_embedding_vector_index")
CHUNK_WORDS = 100
CHUNK_OVERLAP_WORDS = 20
MEMORY_MESSAGES = 5

THREAT_INTELLIGENCE_DOCUMENTS = [
    {
        "source": "cisa-ransomware-response",
        "text": (
            "Ransomware incidents often begin with stolen credentials, exposed remote "
            "services, or malicious email attachments. Threat intelligence teams should "
            "preserve endpoint and identity logs, isolate affected hosts, and identify "
            "the initial access vector before rebuilding systems. Rotate credentials "
            "that may have been exposed and verify offline backups before restoration. "
            "Share indicators of compromise with trusted partners while avoiding "
            "unverified attribution."
        ),
    },
    {
        "source": "mitre-credential-access",
        "text": (
            "Credential access describes techniques adversaries use to steal account "
            "names and passwords. Defensive monitoring can correlate unusual sign-in "
            "locations, repeated authentication failures, new access tokens, and "
            "unexpected privilege changes. Multi-factor authentication reduces the "
            "impact of stolen passwords, while phishing-resistant methods provide "
            "stronger protection. Investigators should revoke suspicious sessions "
            "and review recent account activity."
        ),
    },
    {
        "source": "threat-intelligence-iocs",
        "text": (
            "Indicators of compromise (IOCs) include IP addresses, domains, file "
            "hashes, and behavioral patterns associated with malicious activity. "
            "An IOC is most useful when accompanied by its source, confidence, "
            "timestamp, and expiration or review guidance. A single indicator rarely "
            "proves attribution; defenders should combine it with endpoint telemetry "
            "and network context. Stale indicators can create false positives, so "
            "teams should validate and periodically retire them."
        ),
    },
    {
        "source": "incident-phishing-analysis",
        "text": (
            "Phishing investigations should preserve the original message, including "
            "headers, URLs, and attachment hashes. Analysts can examine sender "
            "authentication results, redirect chains, and file behavior in a safe "
            "sandbox. Block confirmed malicious infrastructure across email and web "
            "controls, then search for related messages and affected accounts. "
            "Employee reporting and rapid triage help limit exposure."
        ),
    },
]


class Embedder(Protocol):
    dimensions: int

    def embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        ...


@dataclass
class VoyageEmbedder:
    client: Any
    model: str
    dimensions: int = 0

    def embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        response = self.client.embed(texts, model=self.model, input_type=input_type)
        vectors = response.embeddings
        if not vectors:
            raise RuntimeError("Voyage AI returned no embeddings.")
        self.dimensions = len(vectors[0])
        return vectors


@dataclass
class SentenceTransformerEmbedder:
    model: Any
    dimensions: int

    def embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        del input_type
        vectors = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()


def create_embedder() -> Embedder:
    """Prefer Voyage when explicitly configured; otherwise use the local model."""
    voyage_key = os.getenv("VOYAGE_API_KEY")
    if voyage_key:
        import voyageai

        return VoyageEmbedder(
            client=voyageai.Client(api_key=voyage_key),
            model=os.getenv("VOYAGE_MODEL", "voyage-3-lite"),
        )

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(
        os.getenv(
            "SENTENCE_TRANSFORMER_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
    )
    return SentenceTransformerEmbedder(model=model, dimensions=model.get_sentence_embedding_dimension())


def chunk_text(
    text: str,
    chunk_words: int = CHUNK_WORDS,
    overlap_words: int = CHUNK_OVERLAP_WORDS,
) -> list[str]:
    if chunk_words <= 0 or overlap_words < 0 or overlap_words >= chunk_words:
        raise ValueError("Require chunk_words > overlap_words >= 0.")
    words = text.split()
    if not words:
        return []
    stride = chunk_words - overlap_words
    chunks = []
    for start in range(0, len(words), stride):
        end = min(start + chunk_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
    return chunks


def build_chunks(documents: list[dict[str, str]]) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    for document in documents:
        for part_number, text in enumerate(chunk_text(document["text"]), start=1):
            chunks.append(
                {
                    "text": text,
                    "source": document["source"],
                    "chunk": str(part_number),
                }
            )
    return chunks


def ensure_vector_index(collection: Any, index_name: str, dimensions: int) -> None:
    definition = {
        "fields": [
            {
                "type": "vector",
                "path": "embedding",
                "numDimensions": dimensions,
                "similarity": "cosine",
            }
        ]
    }
    indexes = list(collection.list_search_indexes(index_name))
    if indexes:
        index_definition = (
            indexes[0].get("latestDefinition")
            or indexes[0].get("definition")
            or {}
        )
        fields = index_definition.get("fields") or [{}]
        existing_dimensions = fields[0].get("numDimensions")
        if existing_dimensions and existing_dimensions != dimensions:
            raise ValueError(
                f"Search index {index_name!r} has {existing_dimensions} dimensions; "
                f"the selected embedder produces {dimensions}."
            )
    else:
        try:
            collection.create_search_index(
                name=index_name,
                definition=definition,
                type="vectorSearch",
            )
        except TypeError:
            collection.create_search_index(
                model={"name": index_name, "definition": definition, "type": "vectorSearch"}
            )
    deadline = time.monotonic() + int(os.getenv("VECTOR_INDEX_WAIT_SECONDS", "120"))
    while time.monotonic() < deadline:
        current = list(collection.list_search_indexes(index_name))
        if current and current[0].get("queryable"):
            return
        time.sleep(2)
    raise TimeoutError(
        f"MongoDB vector search index {index_name!r} did not become queryable before timeout."
    )


def vector_search(
    collection: Any,
    query_vector: list[float],
    index_name: str = VECTOR_INDEX_NAME,
) -> list[dict[str, Any]]:
    pipeline = [
        {
            "$vectorSearch": {
                "index": index_name,
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": 20,
                "limit": 3,
            }
        },
        {
            "$project": {
                "_id": 0,
                "text": 1,
                "source": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    return list(collection.aggregate(pipeline))


def fetch_recent_messages(collection: Any, user_id: str) -> list[dict[str, str]]:
    records = list(
        collection.find(
            {"user_id": user_id},
            {"_id": 0, "role": 1, "content": 1, "timestamp": 1},
        )
        .sort("timestamp", -1)
        .limit(MEMORY_MESSAGES)
    )
    return [
        {"role": record["role"], "content": record["content"]}
        for record in reversed(records)
    ]


def construct_prompt(
    question: str,
    retrieved: list[dict[str, Any]],
    history: list[dict[str, str]],
) -> list[dict[str, str]]:
    context = "\n\n".join(
        f"[{item.get('source', 'unknown')}]\n{item['text']}" for item in retrieved
    )
    system = (
        "Answer the user using the supplied threat-intelligence context and recent "
        "conversation. Distinguish evidence from uncertainty. If the context does not "
        "support an answer, say so. Do not invent indicators or attribution.\n\n"
        f"Retrieved context:\n{context or '(No matching documents were retrieved.)'}"
    )
    return [{"role": "system", "content": system}, *history, {"role": "user", "content": question}]


def simulate_answer(messages: list[dict[str, str]]) -> str:
    user_message = messages[-1]["content"]
    context = messages[0]["content"].split("Retrieved context:\n", maxsplit=1)[-1]
    if context.startswith("(No matching documents"):
        return "I could not find supporting information in the indexed threat-intelligence documents."
    first_chunk = context.split("\n\n", maxsplit=1)[0].split("\n", maxsplit=1)[-1]
    sentences = re.split(r"(?<=[.!?])\s+", first_chunk)
    answer = " ".join(sentences[:2]).strip()
    return (
        f"Based on the retrieved threat-intelligence material, {answer} "
        f"(Question considered: {user_message})"
    )


def generate_answer(messages: list[dict[str, str]]) -> str:
    endpoint = os.getenv("LLM_API_URL")
    if not endpoint:
        return simulate_answer(messages)

    payload = json.dumps(
        {"model": os.getenv("LLM_MODEL", "gpt-4o-mini"), "messages": messages}
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("LLM_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"LLM API request failed: {error}") from error
    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("LLM API response did not contain choices[0].message.content.") from error


def index_documents(collection: Any, embedder: Embedder) -> None:
    chunks = build_chunks(THREAT_INTELLIGENCE_DOCUMENTS)
    vectors = embedder.embed([chunk["text"] for chunk in chunks], input_type="document")
    if len(vectors) != len(chunks):
        raise RuntimeError("Embedding provider returned a different number of vectors than chunks.")
    if not vectors:
        raise RuntimeError("No document embeddings were generated.")
    ensure_vector_index(collection, VECTOR_INDEX_NAME, len(vectors[0]))
    sources = [document["source"] for document in THREAT_INTELLIGENCE_DOCUMENTS]
    collection.delete_many({"source": {"$in": sources}})
    collection.insert_many(
        [{**chunk, "embedding": vector} for chunk, vector in zip(chunks, vectors)]
    )


def answer_question(
    database: Any,
    user_id: str,
    question: str,
    embedder: Embedder,
) -> str:
    documents = database[DOCUMENT_COLLECTION]
    conversations = database[CONVERSATION_COLLECTION]
    history = fetch_recent_messages(conversations, user_id)
    query_vector = embedder.embed([question], input_type="query")[0]
    retrieved = vector_search(documents, query_vector)
    now = datetime.now(timezone.utc)
    conversations.insert_one(
        {"user_id": user_id, "timestamp": now, "role": "user", "content": question}
    )
    answer = generate_answer(construct_prompt(question, retrieved, history))
    conversations.insert_one(
        {
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc),
            "role": "assistant",
            "content": answer,
        }
    )
    return answer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", default=os.getenv("RAG_USER_ID", "student"))
    parser.add_argument("--question", help="Question to answer; prompts interactively if omitted.")
    parser.add_argument("--skip-indexing", action="store_true", help="Reuse documents already in Atlas.")
    args = parser.parse_args()
    question = args.question or input("Threat-intelligence question: ").strip()
    if not question:
        parser.error("A non-empty --question is required.")

    mongo_uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
    if not mongo_uri:
        parser.error("Set MONGO_URI or MONGODB_URI to a MongoDB Atlas connection string.")
    if mongo_uri.startswith("PASTE_YOUR_"):
        parser.error("Replace the MONGO_URI placeholder in the project .env file with an Atlas URI.")

    embedder = create_embedder()
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10_000)
    try:
        client.admin.command("ping")
        database = client[DATABASE_NAME]
        if not args.skip_indexing:
            index_documents(database[DOCUMENT_COLLECTION], embedder)
        answer = answer_question(database, args.user_id, question, embedder)
        print(answer)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
