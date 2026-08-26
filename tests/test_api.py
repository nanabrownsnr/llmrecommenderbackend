import io
import zipfile

from fastapi.testclient import TestClient

from app.main import app

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
        assert {"docker-compose.yml", "deployment.env", "Start.cmd", "Stop.cmd", "Restart.cmd"} <= names
        compose = archive.read("docker-compose.yml").decode()
        environment = archive.read("deployment.env").decode()
        assert "127.0.0.1:${OLLAMA_PORT}:11434" in compose
        assert "127.0.0.1:${NGROK_API_PORT}:4040" in compose
        assert "ngrok/ngrok:latest" in compose
        assert "--web-addr" not in compose
        assert "NGROK_AUTHTOKEN: ${NGROK_AUTHTOKEN}" in compose
        assert "OLLAMA_MODEL=qwen2.5:3b" in environment
        assert "OLLAMA_PORT=11434" in environment
        assert "NGROK_API_PORT=4040" in environment
        assert "NGROK_AUTHTOKEN=test_ngrok_authtoken_1234567890" in environment
        start_script = archive.read("scripts/start.ps1").decode()
        assert 'cmd.exe /d /c "docker info 1>nul 2>nul"' in start_script
        assert "Find-AvailablePort" in start_script


def test_reject_unsupported_deployment() -> None:
    response = client.post("/api/deployments", json={**DEPLOYMENT_REQUEST, "platform": "linux"})
    assert response.status_code == 400


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
