"""Compare FAISS HNSW and IVF cosine indexes against exact search."""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import numpy as np


load_dotenv(Path(__file__).with_name(".env"), override=False)

DOCUMENT_COUNT = 5_000
DIMENSIONS = 384
QUERY_COUNT = 100
TOP_K = 20
BATCH_SIZE = 250
RESULTS_PATH = Path(os.getenv("BENCHMARK_RESULTS_PATH", "benchmark_results.json"))

WIKIPEDIA_STYLE_TEMPLATES = [
    "The {subject} is a {category} studied for its role in {field}, with research published in {year}.",
    "Researchers at {place} examined how {subject} affects {field} using a {method} approach.",
    "Historical records describe {subject} as an important example of {category} in {region}.",
    "A recent analysis of {subject} compared observations from {year} with earlier work on {field}.",
    "The {method} method is commonly used to investigate {category} and related questions in {field}.",
]
VOCABULARY = {
    "subject": ["river systems", "urban growth", "coral reefs", "solar energy", "migration patterns",
                "ancient trade", "forest ecology", "public health", "language change", "volcanic ash"],
    "category": ["regional phenomenon", "scientific topic", "historical process", "social trend",
                 "environmental factor", "technical development"],
    "field": ["climate science", "archaeology", "biology", "economics", "geography", "astronomy"],
    "year": ["1998", "2006", "2014", "2021", "the twentieth century", "recent decades"],
    "place": ["the University of Bergen", "a regional institute", "the national archive",
              "a coastal observatory", "the research center"],
    "method": ["statistical", "comparative", "geospatial", "longitudinal", "laboratory"],
    "region": ["the northern plateau", "the Mediterranean", "central Asia", "the Pacific basin"],
}


def make_sentences(count: int, seed: int, prefix: str = "") -> list[str]:
    generator = random.Random(seed)
    sentences = []
    for _ in range(count):
        template = generator.choice(WIKIPEDIA_STYLE_TEMPLATES)
        values = {key: generator.choice(options) for key, options in VOCABULARY.items()}
        sentences.append(prefix + template.format(**values))
    return sentences


def embed_sentences(sentences: list[str], model_name: str) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    vectors = model.encode(
        sentences,
        batch_size=64,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    vectors = np.ascontiguousarray(vectors, dtype=np.float32)
    if vectors.shape != (len(sentences), DIMENSIONS):
        raise ValueError(
            f"Expected vectors of shape ({len(sentences)}, {DIMENSIONS}), got {vectors.shape}."
        )
    return vectors


def persist_corpus(
    mongo_uri: str,
    database_name: str,
    sentences: list[str],
    vectors: np.ndarray,
) -> None:
    from pymongo import MongoClient

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10_000)
    try:
        client.admin.command("ping")
        collection = client[database_name]["benchmark_documents"]
        collection.delete_many({"dataset_id": "exercise17-v1"})
        for offset in range(0, len(sentences), BATCH_SIZE):
            end = min(offset + BATCH_SIZE, len(sentences))
            collection.insert_many(
                [
                    {
                        "dataset_id": "exercise17-v1",
                        "text": sentences[index],
                        "embedding": vectors[index].tolist(),
                    }
                    for index in range(offset, end)
                ],
                ordered=False,
            )
    finally:
        client.close()


def exact_top_k(corpus: np.ndarray, queries: np.ndarray, top_k: int) -> np.ndarray:
    scores = queries @ corpus.T
    return np.argpartition(scores, -top_k, axis=1)[:, -top_k:]


def recall_at_k(approximate: np.ndarray, exact: np.ndarray) -> float:
    matches = [
        len(set(approximate_row.tolist()) & set(exact_row.tolist())) / exact.shape[1]
        for approximate_row, exact_row in zip(approximate, exact)
    ]
    return float(statistics.mean(matches))


def benchmark_index(
    name: str,
    index: Any,
    corpus: np.ndarray,
    queries: np.ndarray,
    exact: np.ndarray,
) -> dict[str, Any]:
    build_start = time.perf_counter()
    if name == "HNSW":
        index.hnsw.efConstruction = 64
        index.add(corpus)
        index.hnsw.efSearch = 64
    else:
        index.train(corpus)
        index.add(corpus)
        index.nprobe = 10
    build_seconds = time.perf_counter() - build_start

    latencies: list[float] = []
    found: list[np.ndarray] = []
    for query in queries:
        started = time.perf_counter()
        _, ids = index.search(query.reshape(1, -1), TOP_K)
        latencies.append(time.perf_counter() - started)
        found.append(ids[0])
    return {
        "index": name,
        "build_time_seconds": build_seconds,
        "avg_query_latency_ms": statistics.mean(latencies) * 1000,
        "recall_at_20_percent": recall_at_k(np.stack(found), exact) * 100,
    }


def run_benchmark(
    corpus: np.ndarray,
    queries: np.ndarray,
) -> list[dict[str, Any]]:
    import faiss

    if corpus.ndim != 2 or corpus.shape[1] != DIMENSIONS:
        raise ValueError(f"Corpus must have shape (n, {DIMENSIONS}).")
    if len(corpus) < 100:
        raise ValueError("At least 100 vectors are needed for the IVF benchmark.")
    if len(queries) != QUERY_COUNT:
        raise ValueError(f"Expected exactly {QUERY_COUNT} benchmark queries.")

    exact = exact_top_k(corpus, queries, TOP_K)
    hnsw = faiss.IndexHNSWFlat(DIMENSIONS, 16, faiss.METRIC_INNER_PRODUCT)
    ivf = faiss.IndexIVFFlat(
        faiss.IndexFlatIP(DIMENSIONS), DIMENSIONS, 100, faiss.METRIC_INNER_PRODUCT
    )
    return [
        benchmark_index("HNSW", hnsw, corpus, queries, exact),
        benchmark_index("IVF", ivf, corpus, queries, exact),
    ]


def print_results(results: list[dict[str, Any]]) -> None:
    print(f"{'Index':<10} {'Build Time (s)':>16} {'Avg Query (ms)':>16} {'Recall@20 (%)':>16}")
    print("-" * 62)
    for row in results:
        print(
            f"{row['index']:<10} {row['build_time_seconds']:>16.4f} "
            f"{row['avg_query_latency_ms']:>16.4f} "
            f"{row['recall_at_20_percent']:>16.2f}"
        )
    print(
        f"\nSummary: {len(results)} indexes; "
        f"mean build={statistics.mean(r['build_time_seconds'] for r in results):.4f}s, "
        f"mean latency={statistics.mean(r['avg_query_latency_ms'] for r in results):.4f}ms, "
        f"mean Recall@20={statistics.mean(r['recall_at_20_percent'] for r in results):.2f}%."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-mongodb",
        action="store_true",
        help="Run the local FAISS benchmark without persisting the corpus to MongoDB.",
    )
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()

    mongo_uri = None
    if not args.skip_mongodb:
        mongo_uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
        if not mongo_uri:
            parser.error("Set MONGO_URI or MONGODB_URI, or pass --skip-mongodb.")
        if mongo_uri.startswith("PASTE_YOUR_"):
            parser.error("Replace the MONGO_URI placeholder in the project .env file with an Atlas URI.")

    model_name = os.getenv(
        "SENTENCE_TRANSFORMER_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    print(f"Generating and embedding {DOCUMENT_COUNT} benchmark documents...")
    documents = make_sentences(DOCUMENT_COUNT, args.seed)
    queries = make_sentences(QUERY_COUNT, args.seed + 1, prefix="In a related study, ")
    corpus_vectors = embed_sentences(documents, model_name)
    query_vectors = embed_sentences(queries, model_name)

    if not args.skip_mongodb:
        assert mongo_uri is not None
        persist_corpus(
            mongo_uri,
            os.getenv("MONGODB_DATABASE", "rag_demo"),
            documents,
            corpus_vectors,
        )
        print("Inserted the corpus into MongoDB in batches.")

    results = run_benchmark(corpus_vectors, query_vectors)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "document_count": len(documents),
        "embedding_dimensions": DIMENSIONS,
        "query_count": len(queries),
        "top_k": TOP_K,
        "metric": "cosine",
        "results": results,
    }
    RESULTS_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_results(results)
    print(f"\nWrote benchmark results to {RESULTS_PATH.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
