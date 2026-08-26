from app.domain.catalog import CatalogModel
from app.domain.hardware import NormalizedHardware
from app.schemas import UseCase
WEIGHTS = {"all": (.40, .35, .15, .10), "chat": (.40, .40, .15, .05), "coding": (.55, .20, .15, .10), "reasoning": (.60, .15, .10, .15), "writing": (.50, .25, .15, .10), "fast": (.25, .55, .15, .05)}
def score_model(model: CatalogModel, hardware: NormalizedHardware, use_case: UseCase, capacity_gb: float) -> tuple[float, str]:
    ratio = model.estimated_runtime_gb / max(capacity_gb, .01); fit = max(0., min(100., 100 - abs(.72 - ratio) * 180)); speed = max(0., min(100., 100 - model.estimated_runtime_gb * 9 + hardware.cpu_threads * 1.5))
    if hardware.gpu_detected: speed = min(100., speed + 8)
    context = max(0., min(100., model.context_length / 32768 * 100)); quality = max(0., min(100., model.quality_score)); q, s, f, c = WEIGHTS[use_case.value]
    return quality * q + speed * s + fit * f + context * c, ("recommended" if use_case.value == "all" or use_case.value in model.use_cases else "compatible")
