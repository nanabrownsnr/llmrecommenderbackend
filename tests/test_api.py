import io
import zipfile

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import Hardware, RecommendationRequest

client = TestClient(app)
DEPLOYMENT_REQUEST = {
    "modelId": "qwen2.5",
    "ollamaTag": "qwen2.5:3b",
    "platform": "windows",
    "architecture": "x64",
    "packageType": "docker-compose",
    "enableTunnel": True,
    "ngrokAuthtoken": "test_ngrok_authtoken_1234567890",
}


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_default_memory_utilization_is_thirty_percent() -> None:
    assert RecommendationRequest.model_fields["memory_utilization"].default == 0.3


def test_unavailable_memory_defaults_to_eight_gb() -> None:
    base_hardware = {
        "cpu": {"logicalThreads": 8, "model": "Browser access restricted"},
        "system": {"platform": "MacIntel", "architecture": "x64", "bitness": "64"},
        "gpu": {"status": "unknown", "confidence": "low", "renderer": "unknown"},
    }
    assert Hardware.model_validate(base_hardware).memory.approximate_gb == 8
    assert Hardware.model_validate({**base_hardware, "memory": None}).memory.approximate_gb == 8
    assert Hardware.model_validate({**base_hardware, "memory": {"approximateGB": "unavailable"}}).memory.approximate_gb == 8


def test_cors_preflight() -> None:
    response = client.options(
        "/api/deployments",
        headers={
            "Origin": "https://frontend.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


def test_recommend_models() -> None:
    response = client.post("/api/recommendations", json={"hardware": {"cpu": {"logicalThreads": 8, "model": "Browser access restricted"}, "memory": {"approximateGB": 8}, "system": {"platform": "Windows", "architecture": "x86_64", "bitness": "64"}, "gpu": {"status": "GPU detected", "confidence": "High", "renderer": "ANGLE"}}, "useCase": "coding", "memoryUtilization": 0.5})
    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"]["coding"]
    assert "chat" in body["recommendations"]
    assert "nextCursors" in body
    assert all(
        variant["score"] >= 70
        for recommendations in body["recommendations"].values()
        for model in recommendations
        for variant in model["variants"]
    )
    assert all(
        len(model["variants"]) <= 3
        for recommendations in body["recommendations"].values()
        for model in recommendations
    )


def test_generate_windows_package() -> None:
    response = client.post("/api/deployments", json=DEPLOYMENT_REQUEST)
    assert response.status_code == 200
    assert response.json()["filename"] == "deploy-qwen2.5-3b-windows.zip"
    assert response.json()["downloadUrl"].endswith(f"/download")
    download = client.get(response.json()["downloadUrl"])
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        assert {"docker-compose.yml", "deployment.env", "Start.cmd", "Stop.cmd", "Restart.cmd", "Show URL.cmd", "scripts/show-url.ps1"} <= names
        compose = archive.read("docker-compose.yml").decode()
        environment = archive.read("deployment.env").decode()
        assert "127.0.0.1:${OLLAMA_PORT}:11434" in compose
        assert "127.0.0.1:${NGROK_API_PORT}:4040" in compose
        assert "ngrok/ngrok:latest" in compose
        assert "--web-addr" not in compose
        assert "NGROK_AUTHTOKEN: ${NGROK_AUTHTOKEN}" in compose
        assert "OLLAMA_KEEP_ALIVE: 24h" in compose
        assert "OLLAMA_MODEL=qwen2.5:3b" in environment
        assert "OLLAMA_PORT=11434" in environment
        assert "NGROK_API_PORT=4040" in environment
        assert "NGROK_AUTHTOKEN=test_ngrok_authtoken_1234567890" in environment
        start_script = archive.read("scripts/start.ps1").decode()
        assert 'cmd.exe /d /c "docker info 1>nul 2>nul"' in start_script
        assert "Find-AvailablePort" in start_script
        assert 'keep_alive = "24h"' in start_script
        assert 'OpenAI-compatible API base URL: $apiBaseUrl' in start_script
        show_url_script = archive.read("scripts/show-url.ps1").decode()
        assert 'TrimEnd(\'/\'))/v1' in show_url_script
        assert "Set-Clipboard -Value $apiBaseUrl" in show_url_script


def test_reject_unsupported_deployment() -> None:
    response = client.post("/api/deployments", json={**DEPLOYMENT_REQUEST, "platform": "solaris"})
    assert response.status_code == 400


def test_accept_windows_deployment_regardless_of_architecture() -> None:
    for architecture in ("x86", "x64", "x86_64", "arm64"):
        response = client.post(
            "/api/deployments",
            json={**DEPLOYMENT_REQUEST, "architecture": architecture},
        )
        assert response.status_code == 200


def test_generate_linux_package() -> None:
    response = client.post(
        "/api/deployments",
        json={**DEPLOYMENT_REQUEST, "platform": "linux", "architecture": "arm64"},
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "deploy-qwen2.5-3b-linux.zip"
    download = client.get(response.json()["downloadUrl"])
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        assert {"Start.sh", "Stop.sh", "Restart.sh", "Show URL.sh", "scripts/start.sh"} <= names
        assert "Start.cmd" not in names
        assert archive.getinfo("Start.sh").external_attr >> 16 & 0o111 == 0o111
        start_script = archive.read("scripts/start.sh").decode()
        assert "find_available_port" in start_script
        assert '"keep_alive":"24h"' in start_script
        assert '${public_url%/}/v1' in start_script


def test_generate_macos_package_from_apple_alias() -> None:
    response = client.post(
        "/api/deployments",
        json={**DEPLOYMENT_REQUEST, "platform": "apple", "architecture": "arm64"},
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "deploy-qwen2.5-3b-macos.zip"
    download = client.get(response.json()["downloadUrl"])
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        assert {"Start.command", "Stop.command", "Restart.command", "Show URL.command", "scripts/start.sh"} <= names
        assert archive.getinfo("Start.command").external_attr >> 16 & 0o111 == 0o111
        readme = archive.read("README.txt").decode()
        assert "right-click Start.command" in readme
        assert "Apple Metal acceleration" in readme


def test_generate_macos_package_from_macintel_platform() -> None:
    response = client.post(
        "/api/deployments",
        json={**DEPLOYMENT_REQUEST, "platform": "MacIntel", "architecture": "x64"},
    )
    assert response.status_code == 200
    assert response.json()["filename"].endswith("-macos.zip")


def test_reject_unknown_model() -> None:
    response = client.post("/api/deployments", json={**DEPLOYMENT_REQUEST, "modelId": "unknown", "ollamaTag": "unknown-model:99b"})
    assert response.status_code == 404


def test_require_ngrok_authtoken() -> None:
    payload = {key: value for key, value in DEPLOYMENT_REQUEST.items() if key != "ngrokAuthtoken"}
    response = client.post("/api/deployments", json=payload)
    assert response.status_code == 422


def test_reject_invalid_ngrok_authtoken_without_echoing_it() -> None:
    secret = "invalid token value"
    response = client.post("/api/deployments", json={**DEPLOYMENT_REQUEST, "ngrokAuthtoken": secret})
    assert response.status_code == 400
    assert secret not in response.text


def test_public_base_url_override(monkeypatch) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://api.example.com/")
    response = client.post("/api/deployments", json=DEPLOYMENT_REQUEST)
    assert response.status_code == 200
    assert response.json()["downloadUrl"].startswith("https://api.example.com/api/deployments/")
