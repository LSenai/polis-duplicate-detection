#!/usr/bin/env bash
# Enable pgvector and run migrations for the local Docker DB.
# Run from repo root after: docker compose up -d
set -e
cd "$(dirname "$0")/.."
echo "Enabling pgvector extension..."
docker compose exec -T db psql -U polis_dup -d duplicate_detection -c "CREATE EXTENSION IF NOT EXISTS vector;"
echo "Running migration 001_comment_embeddings.sql..."
docker compose exec -T db psql -U polis_dup -d duplicate_detection < migrations/001_comment_embeddings.sql
echo "DB setup complete."
