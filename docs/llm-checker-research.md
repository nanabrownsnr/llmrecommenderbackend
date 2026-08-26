# LLM Checker integration

The repository vendors LLM Checker's offline SQLite snapshot at:

`vendor/llm-checker/src/data/seed/models.db`

API 1 reads this database through a read-only adapter and immediately maps its `models` and `variants` tables into our provider-neutral catalog model. The public API and scoring layer do not depend on LLM Checker table names.

The snapshot is the required API 1 data source. A missing or invalid snapshot should fail clearly rather than silently replacing the catalog with a smaller fallback.

`LLM_CHECKER_DB_PATH` can override the vendored path for development or snapshot updates.

LLM Checker documents a Quality/Speed/Fit/Context scoring model, quantization-aware memory estimates, and SQLite-backed Ollama catalog. Our scorer independently implements the documented behavior.

The vendored project includes its `LICENSE` and seed README. Keep the database and attribution with the project. Monetized hosted/API use requires separate commercial permission under the upstream NPDL-1.0 license.
