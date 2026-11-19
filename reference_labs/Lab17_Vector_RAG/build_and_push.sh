#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${DOCKER_IMAGE:-yourusername/mongodb-rag-lab17:latest}"

docker build --tag "$IMAGE_TAG" .
docker push "$IMAGE_TAG"
