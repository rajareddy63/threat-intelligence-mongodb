"""Focused tests for pure project behavior; no database or model download required."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import numpy as np

import generate_pdf
import lab17_1_rag
import lab17_2_benchmark


class ChunkingTests(unittest.TestCase):
    def test_sliding_chunks_have_configured_overlap(self):
        words = [f"word{i}" for i in range(11)]
        chunks = lab17_1_rag.chunk_text(" ".join(words), chunk_words=5, overlap_words=2)
        self.assertEqual(chunks, ["word0 word1 word2 word3 word4", "word3 word4 word5 word6 word7", "word6 word7 word8 word9 word10"])

    def test_chunking_rejects_invalid_overlap(self):
        with self.assertRaises(ValueError):
            lab17_1_rag.chunk_text("text", chunk_words=4, overlap_words=4)


class RagPromptTests(unittest.TestCase):
    def test_prompt_contains_memory_and_retrieved_context(self):
        prompt = lab17_1_rag.construct_prompt(
            "What should we do?",
            [{"source": "incident-guide", "text": "Preserve identity logs."}],
            [{"role": "user", "content": "We saw a suspicious sign-in."}],
        )
        self.assertIn("incident-guide", prompt[0]["content"])
        self.assertEqual(prompt[1]["content"], "We saw a suspicious sign-in.")
        self.assertEqual(prompt[-1]["content"], "What should we do?")

    def test_vector_search_uses_required_parameters(self):
        collection = Mock()
        collection.aggregate.return_value = []
        lab17_1_rag.vector_search(collection, [0.1, 0.2])
        pipeline = collection.aggregate.call_args.args[0]
        self.assertEqual(pipeline[0]["$vectorSearch"]["numCandidates"], 20)
        self.assertEqual(pipeline[0]["$vectorSearch"]["limit"], 3)

    def test_ensure_vector_index_uses_definition_api_when_available(self):
        collection = Mock()
        collection.list_search_indexes.side_effect = [[], [{"queryable": True}]]
        lab17_1_rag.ensure_vector_index(collection, "demo_index", 12)
        kwargs = collection.create_search_index.call_args.kwargs
        self.assertEqual(kwargs["name"], "demo_index")
        self.assertEqual(kwargs["type"], "vectorSearch")
        self.assertEqual(kwargs["definition"]["fields"][0]["numDimensions"], 12)


class BenchmarkTests(unittest.TestCase):
    def test_recall_at_k(self):
        approximate = np.array([[1, 2, 3], [4, 5, 6]])
        exact = np.array([[1, 2, 9], [4, 8, 6]])
        self.assertAlmostEqual(lab17_2_benchmark.recall_at_k(approximate, exact), 2 / 3)

    def test_repeatable_sentence_generation(self):
        self.assertEqual(
            lab17_2_benchmark.make_sentences(5, seed=17),
            lab17_2_benchmark.make_sentences(5, seed=17),
        )

    def test_hnsw_and_ivf_benchmark_with_synthetic_vectors(self):
        rng = np.random.default_rng(17)
        corpus = rng.normal(size=(5000, lab17_2_benchmark.DIMENSIONS)).astype(np.float32)
        corpus /= np.linalg.norm(corpus, axis=1, keepdims=True)
        queries = rng.normal(size=(lab17_2_benchmark.QUERY_COUNT, lab17_2_benchmark.DIMENSIONS)).astype(np.float32)
        queries /= np.linalg.norm(queries, axis=1, keepdims=True)
        results = lab17_2_benchmark.run_benchmark(corpus, queries)
        self.assertEqual([row["index"] for row in results], ["HNSW", "IVF"])
        for result in results:
            self.assertGreaterEqual(result["build_time_seconds"], 0)
            self.assertGreater(result["avg_query_latency_ms"], 0)
            self.assertGreaterEqual(result["recall_at_20_percent"], 0)
            self.assertLessEqual(result["recall_at_20_percent"], 100)


class PdfTests(unittest.TestCase):
    def test_missing_benchmark_results_are_not_fabricated(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = generate_pdf.load_benchmark_rows(Path(directory) / "missing.json")
        self.assertEqual(rows[0][1:], ["Not run", "Not run", "Not run"])
        self.assertEqual(rows[1][1:], ["Not run", "Not run", "Not run"])

    def test_benchmark_values_appear_in_submission_table(self):
        result = {
            "results": [
                {
                    "index": "HNSW",
                    "build_time_seconds": 1.25,
                    "avg_query_latency_ms": 0.5,
                    "recall_at_20_percent": 98.0,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark_results.json"
            path.write_text(json.dumps(result), encoding="utf-8")
            rows = generate_pdf.load_benchmark_rows(path)
        self.assertEqual(rows[0], ["HNSW", "1.2500 s", "0.5000 ms", "98.00%"])

    def test_demonstration_output_uses_recorded_benchmark_values(self):
        result = {
            "document_count": 5000,
            "embedding_dimensions": 384,
            "query_count": 100,
            "top_k": 20,
            "metric": "cosine",
            "results": [
                {
                    "index": "HNSW",
                    "build_time_seconds": 1.25,
                    "avg_query_latency_ms": 0.5,
                    "recall_at_20_percent": 98.0,
                },
                {
                    "index": "IVF",
                    "build_time_seconds": 0.5,
                    "avg_query_latency_ms": 0.25,
                    "recall_at_20_percent": 96.0,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark_results.json"
            path.write_text(json.dumps(result), encoding="utf-8")
            output = generate_pdf.load_benchmark_output(path)
        self.assertIn("documents=5000", output)
        self.assertIn("HNSW", output)
        self.assertIn("98.00%", output)
        self.assertIn("Recall@20=97.00%", output)


if __name__ == "__main__":
    unittest.main()
