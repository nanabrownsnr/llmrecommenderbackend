"""Read-only adapter for a permitted LLM Checker SQLite snapshot."""
import os, sqlite3
from pathlib import Path
from app.catalog.ollama import _number, _bytes_per_param, _infer_use_cases
from app.domain.catalog import CatalogModel

class LLMCheckerCatalog:
    def __init__(self, path: str | None = None) -> None:
        configured = path or os.getenv("LLM_CHECKER_DB_PATH") or str(Path(__file__).parents[2] / "vendor" / "llm-checker" / "src" / "data" / "seed" / "models.db")
        self.path = Path(configured)
        if not self.path.exists(): raise FileNotFoundError(f"LLM Checker database not found: {self.path}")
    def all(self) -> list[CatalogModel]:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "variants" in tables and "models" in tables:
                rows = db.execute("SELECT v.*, m.name AS model_name, m.family AS model_family, m.description AS model_description FROM variants v JOIN models m ON m.id = v.model_id").fetchall()
            else:
                rows = db.execute("SELECT * FROM models").fetchall()
        models = []
        for row in rows:
            normalized = self._normalize(dict(row))
            if normalized.estimated_runtime_gb > 0 and normalized.size_gb > 0:
                models.append(normalized)
        return models
    @staticmethod
    def _value(row, *names):
        return next((row[name] for name in names if name in row and row[name] not in (None, "")), None)
    def _normalize(self, row):
        tag = str(self._value(row, "ollama_tag", "tag", "name", "model", "canonical_model_id")); params = _number(self._value(row, "parameter_count_b", "params_b", "parameter_size", "parameters"))
        size = float(self._value(row, "size_gb", "size_bytes", "size") or 0); size = size / (1024 ** 3) if size > 100 else size; quant = self._value(row, "quantization", "quantization_level", "quant")
        runtime = float(self._value(row, "estimated_runtime_gb", "runtime_gb") or (params * _bytes_per_param(quant) if params else size * 1.2)); uses = self._value(row, "use_cases", "tasks", "categories")
        uses = tuple(x.strip() for x in uses.replace(";", ",").split(",") if x.strip()) if isinstance(uses, str) else tuple(uses or _infer_use_cases(tag))
        base_id = str(self._value(row, "model_id") or tag.split(":", 1)[0])
        return CatalogModel(base_id, str(self._value(row, "model_name", "display_name", "name", "model") or base_id), tag, str(self._value(row, "family", "model_family") or base_id), params, round(size, 3), round(runtime, 3), quant, int(self._value(row, "context_length", "context") or 4096), uses, float(self._value(row, "quality_score", "quality") or 60), str(self._value(row, "model_description", "description", "summary") or "Ollama model."))
