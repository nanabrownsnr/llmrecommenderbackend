from dataclasses import dataclass

from app.schemas import Hardware


@dataclass(frozen=True)
class NormalizedHardware:
    ram_gb: float
    vram_gb: float
    cpu_threads: int
    platform: str
    architecture: str
    bitness: int | None
    gpu_detected: bool
    gpu_confidence: str
    gpu_renderer: str


def normalize_hardware(hardware: Hardware) -> NormalizedHardware:
    """Convert browser-scanned hardware into stable scorer inputs.

    Browser GPU detection does not reliably expose VRAM, so vram_gb remains zero
    until the client provides a measured value or a later enrichment step adds it.
    """
    bitness = None
    digits = "".join(character for character in hardware.system.bitness if character.isdigit())
    if digits in {"32", "64"}:
        bitness = int(digits)
    detected = hardware.gpu.status.strip().lower() not in {"", "none", "not detected", "unavailable"}
    return NormalizedHardware(
        ram_gb=hardware.memory.approximate_gb,
        vram_gb=0.0,
        cpu_threads=hardware.cpu.logical_threads,
        platform=hardware.system.platform.strip().lower(),
        architecture=hardware.system.architecture.strip().lower(),
        bitness=bitness,
        gpu_detected=detected,
        gpu_confidence=hardware.gpu.confidence.strip().lower(),
        gpu_renderer=hardware.gpu.renderer,
    )
