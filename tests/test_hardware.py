from app.domain.hardware import normalize_hardware
from app.schemas import Hardware


def test_normalize_browser_hardware() -> None:
    hardware = Hardware.model_validate({
        "cpu": {"logicalThreads": 8, "model": "Browser access restricted"},
        "memory": {"approximateGB": 8},
        "system": {"platform": "Windows", "architecture": "x86_64", "bitness": "64"},
        "gpu": {"status": "GPU detected", "confidence": "High", "renderer": "ANGLE"},
    })
    normalized = normalize_hardware(hardware)
    assert normalized.ram_gb == 8
    assert normalized.cpu_threads == 8
    assert normalized.platform == "windows"
    assert normalized.bitness == 64
    assert normalized.gpu_detected is True
