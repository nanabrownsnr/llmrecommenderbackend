from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogModel:
    """Provider-neutral representation of an Ollama catalog entry."""
    model_id: str
    name: str
    ollama_tag: str
    family: str
    parameter_count_b: float | None
    size_gb: float
    estimated_runtime_gb: float
    quantization: str | None
    context_length: int | None
    use_cases: tuple[str, ...]
    quality_score: float
    description: str


CATALOG: tuple[CatalogModel, ...] = (
    CatalogModel("qwen2.5:1.5b", "Qwen 2.5 1.5B", "qwen2.5:1.5b", "qwen2.5", 1.5, 1.1, 1.4, "Q4_K_M", 32768, ("chat", "fast"), 72, "Very fast small model for everyday tasks."),
    CatalogModel("qwen2.5:3b", "Qwen 2.5 3B", "qwen2.5:3b", "qwen2.5", 3, 2.0, 2.4, "Q4_K_M", 32768, ("chat", "coding"), 78, "Strong small model for general use and coding."),
    CatalogModel("llama3.2:3b", "Llama 3.2 3B", "llama3.2:3b", "llama3.2", 3, 2.0, 2.5, "Q4_K_M", 131072, ("chat", "writing"), 77, "Compact general-purpose conversational model."),
    CatalogModel("qwen2.5:7b", "Qwen 2.5 7B", "qwen2.5:7b", "qwen2.5", 7, 4.7, 5.7, "Q4_K_M", 32768, ("coding", "reasoning", "writing"), 84, "More capable model for coding and reasoning."),
)
