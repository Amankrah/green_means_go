# LCA Engineer — Planning Docs

Planning & specification set for evolving the current hand-coded African LCA engine into a database-backed, AI-augmented, ISO-14040/44-compliant **LCA Engineer**.

Read in this order:

1. **[DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)** — vision, the bottlenecks we unlock, architecture, the AI subsystems (matching, RAG, decomposition, anomaly detection), pipeline, roadmap, success metrics. *Start here.*
2. **[DATABASE_PLAN.md](./DATABASE_PLAN.md)** — every database we need (ecoinvent, Agribalyse, ReCiPe, EF, AWARE, IPCC, GLEAM, FAOSTAT…), why, licensing/format, ingestion architecture, and the Tier 1→3 sequencing.
3. **[LITERATURE_WISHLIST.md](./LITERATURE_WISHLIST.md)** — papers, standards, and guidelines to acquire, with access notes and priorities (P0–P2).
4. **[LITERATURE_EXTRACTION.md](./LITERATURE_EXTRACTION.md)** — exactly which sections/tables to extract from each source and the structured schema to store them in.

**Guiding principle:** a deterministic, provenance-tracked Rust core computes; AI subsystems remove the human bottlenecks around it (matching, gap-filling, extraction, QA); Africa-first data fixes the representativeness gap. **Tier 1 is buildable with zero licensing cost** and proves the thesis.

_Authored as LCA Engineer planning output, June 2026._
