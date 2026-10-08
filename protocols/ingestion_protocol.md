# Gazette and Legal-Source Ingestion Protocol v1

1. Discovery is restricted to entries in the versioned source registry.
2. Every request and redirect must satisfy the deny-by-default HTTPS source policy.
3. Downloaded bytes are hashed before metadata registration and stored by SHA-256.
4. Identical bytes reuse the same immutable artifact. A changed hash creates a new source-specific document version linked to the prior record.
5. Source URL, final URL, retrieval timestamp, publication-date value and precision, MIME type, hash and path are retained.
6. Download failures are immutable events and do not stop unrelated sources from being processed.
7. New document records enter `EXTRACTION_QUEUE` and `HUMAN_REVIEW_PENDING`.
8. Ingestion never establishes that a document changed the law. That conclusion requires downstream extraction and human review.
9. The scheduler runs only when explicitly invoked; Phase 1 does not operate an autonomous monitor.
