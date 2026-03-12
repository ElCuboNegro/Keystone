# ADR-0001: Non-AI Deduplication Pipeline

## Context
Massive enterprise repositories often contain duplicate projects, copy-pasted microservices, and redundant solutions. Running an AI over these raw repositories leads to context window exhaustion and unnecessary costs.

## Decision
We will implement mathematical, non-AI tools (MinHash and dependency signature clustering) as the first step in our static analysis pipeline. These tools will run purely locally, using the `datasketch` library for fast LSH (Locality Sensitive Hashing) clustering and extracting manifest structures (`package.json`, `requirements.txt`).

## Consequences
- **Positive:** Massive reduction in token usage. Faster initial repository ingestion. Grouping of redundant microservices without parsing logic.
- **Negative:** Requires new Python dependencies (`datasketch`) in the agentic CI environment. MinHash has a probabilistic nature and might yield false positives at lower thresholds.
