# Phase 5 Amendment Representation and Annotation Protocol

**Status:** Engineering workload implemented; research annotation and taxonomy freeze not performed.

The pipeline creates 50 unique evidence-linked annotation tasks, prioritising internally corroborated amendment events. It preserves the amendment instruction, target snapshot when available, operation, lineage and source evidence. A missing historical before version remains `null` and blocks a complete pair.

Materiality uses only `High`, `Medium`, `Low` and `None`. Two independent annotations, rationales, before/after spans, dimensions, confidence, guideline version and later adjudication must be preserved. Compliance consequence is a separate field. The software never assigns materiality labels or fabricates agreement.

The ten dimensions are a complete technical draft, not a Phase 0 research decision. The guideline cannot become frozen until complete pairs and independent annotations exist and an appropriate agreement analysis is performed.
