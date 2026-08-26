import json, os, urllib.request
from datetime import datetime, timezone
from app.domain.catalog import CatalogModel

DEFAULT_URL = ""
def _number(value):
    if value is None: return None
    if isinstance(value, (int, float)): return float(value)
    text = value.strip().upper().replace(" ", "")
    try: return float(text[:-1]) if text.endswith("B") else float(text)
    except ValueError: return None
def _bytes_per_param(quant): return {"Q8_0": 1.05, "Q4_K_M": 0.58, "Q3_K": 0.48}.get((quant or "").upper(), 0.65)
def _infer_use_cases(tag: str) -> list[str]:
    name = tag.lower(); uses = ["chat"]
    if any(word in name for word in ("code", "coder")): uses.append("coding")
    if any(word in name for word in ("r1", "reason")): uses.append("reasoning")
    if any(word in name for word in ("creative", "mistral", "gemma")): uses.append("writing")
    if any(word in name for word in ("1b", "1.5b", "2b", "3b")): uses.append("fast")
    return list(dict.fromkeys(uses))
def normalize_model(raw: dict) -> CatalogModel:
    details = raw.get("details", raw); tag = raw.get("model") or raw.get("name") or raw.get("tag")
    if not tag: raise ValueError("model entry has no tag")
    parameter_count = _number(details.get("parameter_size") or raw.get("parameter_size")); size_bytes = raw.get("size") or raw.get("size_bytes") or 0
    size_gb = float(size_bytes) / (1024 ** 3) if float(size_bytes) > 100 else float(size_bytes); quant = details.get("quantization_level") or raw.get("quantization")
    estimated = float(raw.get("estimated_runtime_gb") or (parameter_count * _bytes_per_param(quant) if parameter_count else size_gb * 1.2)); family = details.get("family") or tag.split(":", 1)[0]
    return CatalogModel(tag, raw.get("name") or tag.split(":", 1)[0], tag, family, parameter_count, round(size_gb, 3), round(estimated, 3), quant, int(raw.get("context_length") or details.get("context_length") or 4096), tuple(raw.get("use_cases") or _infer_use_cases(tag)), float(raw.get("quality_score") or 60), raw.get("description") or "Ollama model.")
class OllamaCatalogClient:
    def __init__(self, url: str | None = None) -> None: self.url = url or os.getenv("OLLAMA_CATALOG_URL", DEFAULT_URL)
    def fetch(self) -> list[CatalogModel]:
        if not self.url:
            raise RuntimeError("OLLAMA_CATALOG_URL is not configured: Ollama exposes local installed models at /api/tags, not a public all-model catalog endpoint")
        request = urllib.request.Request(self.url, headers={"Accept": "application/json", "User-Agent": "LLMrecommender/0.1"})
        with urllib.request.urlopen(request, timeout=30) as response: payload = json.loads(response.read().decode())
        entries = payload.get("models", payload.get("tags", payload if isinstance(payload, list) else []))
        return [normalize_model(entry) for entry in entries if isinstance(entry, dict) and not entry.get("cloud", False)]
def utc_now() -> str: return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
