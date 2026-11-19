# Exercise-17: AI-Native MongoDB: Vector Search and RAG Foundations

Python implementation for the two labs, Docker packaging, and PDF submission.

## Setup

Use Python 3.11 or newer. Install dependencies and configure environment values:

```shell
python -m pip install -r requirements.txt
cp .env.example .env
```

In PowerShell, use `Copy-Item .env.example .env` for the second command.

Set `MONGO_URI` (or `MONGODB_URI`) in `.env` to an Atlas connection string. Atlas vector search
requires a cluster that supports vector search and permission to create search
indexes. The first RAG run creates its search index and waits for it to become
queryable. It uses Voyage embeddings when `VOYAGE_API_KEY` is configured and
otherwise downloads/uses the configured Sentence Transformers model.

## Lab 17.1: RAG and conversation memory

```shell
python lab17_1_rag.py --user-id student --question "How should I investigate stolen credentials?"
```

The script chunks four built-in threat-intelligence documents into overlapping
100-word windows and stores chunks in `rag_demo.documents`. Per-user messages are
stored in `rag_demo.conversations`; the five most recent turns are included in
the next response prompt. Set `LLM_API_URL` (and optionally `LLM_API_KEY` and
`LLM_MODEL`) to use an OpenAI-compatible chat endpoint. Without it, a local
evidence-based response simulator is used.

## Lab 17.2: HNSW vs. IVF

```shell
python lab17_2_benchmark.py
```

The benchmark generates and embeds 5,000 sentences, persists the corpus to
MongoDB in batches, then runs 100 queries against FAISS HNSW and IVF indexes.
Run `python lab17_2_benchmark.py --skip-mongodb` to execute the local index
comparison without MongoDB. Results are printed and saved in
`benchmark_results.json`. The exact benchmark definitions are also recorded in
`vector_index_definitions.json`.

The algorithm-specific benchmark uses FAISS so HNSW parameters (`M`, `efConstruction`)
and IVF's `nlist` can be controlled exactly. MongoDB Atlas stores the corpus; its
Vector Search index is separately created by the RAG script. The benchmark does
not claim that an Atlas vector index supports the FAISS-specific IVF configuration.
Cosine similarity is implemented by L2-normalizing vectors and using inner product.

## PDF and Docker

```shell
python generate_pdf.py
docker compose build
docker compose run --rm rag --help
```

Docker Hub repository: https://hub.docker.com/r/raja6303/mongodb-rag-lab17

The project image tag is `raja6303/mongodb-rag-lab17:latest`. The image was built
locally; the Docker Hub manifest must be checked to determine whether an upload
completed. `build_and_push.sh` builds and pushes the configured `DOCKER_IMAGE`
after Docker Hub authentication. The PDF reads benchmark measurements when
`benchmark_results.json` exists and labels them "Not run" otherwise. It records
the upload state supplied in `DOCKER_UPLOAD_STATUS`.

## Data and credentials

Keep `.env` and API credentials private. Do not use production collections for
the exercise: the RAG script replaces documents for its four source identifiers,
and the benchmark replaces records with the `exercise17-v1` dataset identifier.
