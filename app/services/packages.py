import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.catalog.llm_checker import LLMCheckerCatalog
from app.schemas import DeploymentRequest, DeploymentResponse

MODEL_TAG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*(?::[A-Za-z0-9][A-Za-z0-9._-]*)?$")
NGROK_AUTHTOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,512}$")


class InvalidDeployment(ValueError):
    pass


class UnknownModel(LookupError):
    pass


@dataclass(frozen=True)
class DeploymentPackage:
    filename: str
    content: bytes
    expires_at: datetime


PACKAGES: dict[str, DeploymentPackage] = {}


def _purge_expired_packages(now: datetime) -> None:
    for deployment_id, package in list(PACKAGES.items()):
        if package.expires_at <= now:
            PACKAGES.pop(deployment_id, None)


def _validate(request: DeploymentRequest) -> None:
    if request.platform.lower() != "windows":
        raise InvalidDeployment("V1 supports Windows only")
    if request.package_type != "docker-compose":
        raise InvalidDeployment("V1 packageType must be docker-compose")
    if not request.enable_tunnel:
        raise InvalidDeployment("V1 requires enableTunnel=true")
    if not NGROK_AUTHTOKEN_PATTERN.fullmatch(request.ngrok_authtoken.get_secret_value()):
        raise InvalidDeployment("Invalid ngrok connection key")
    if not MODEL_TAG_PATTERN.fullmatch(request.ollama_tag):
        raise InvalidDeployment("Invalid Ollama model tag")
    if not any(model.ollama_tag == request.ollama_tag for model in LLMCheckerCatalog().all()):
        raise UnknownModel(f"Unknown Ollama model tag: {request.ollama_tag}")


def _compose() -> str:
    return """services:
  ollama:
    image: ollama/ollama:latest
    container_name: ${DEPLOYMENT_ID}-ollama
    restart: unless-stopped
    environment:
      OLLAMA_HOST: 0.0.0.0:11434
      OLLAMA_KEEP_ALIVE: 24h
    ports:
      - "127.0.0.1:${OLLAMA_PORT}:11434"
    volumes:
      - ollama-models:/root/.ollama
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 5s
      timeout: 5s
      retries: 24

  model-init:
    image: ollama/ollama:latest
    profiles: ["setup"]
    environment:
      OLLAMA_HOST: http://ollama:11434
    entrypoint: ["/bin/ollama"]
    command: ["pull", "${OLLAMA_MODEL}"]
    depends_on:
      ollama:
        condition: service_healthy

  ngrok:
    image: ngrok/ngrok:latest
    container_name: ${DEPLOYMENT_ID}-ngrok
    restart: unless-stopped
    environment:
      NGROK_AUTHTOKEN: ${NGROK_AUTHTOKEN}
    command: ["http", "http://ollama:11434", "--log", "stdout", "--log-format", "json"]
    ports:
      - "127.0.0.1:${NGROK_API_PORT}:4040"
    depends_on:
      ollama:
        condition: service_healthy

volumes:
  ollama-models:
    name: ${DEPLOYMENT_ID}-models
"""


def _start_script() -> str:
    return r'''$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Show-Failure([string]$Message) {
    Write-Host ""
    Write-Host "Deployment could not continue:" -ForegroundColor Red
    Write-Host $Message -ForegroundColor Yellow
    exit 1
}

function Test-PortAvailable([int]$Port) {
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        return $true
    } catch { return $false }
    finally { if ($listener) { try { $listener.Stop() } catch {} } }
}

function Find-AvailablePort([int]$PreferredPort) {
    for ($port = $PreferredPort; $port -le [Math]::Min(65535, $PreferredPort + 200); $port++) {
        if (Test-PortAvailable $port) { return $port }
    }
    Show-Failure "No available local port was found near $PreferredPort."
}

function Get-EnvValue([string]$Name, [string]$DefaultValue) {
    $line = Get-Content deployment.env | Where-Object { $_ -like "$Name=*" } | Select-Object -First 1
    if ($line) { return $line.Substring($Name.Length + 1) }
    return $DefaultValue
}

function Set-EnvValue([string]$Name, [string]$Value) {
    $lines = @(Get-Content deployment.env)
    $found = $false
    $updated = foreach ($line in $lines) {
        if ($line -like "$Name=*") { "$Name=$Value"; $found = $true } else { $line }
    }
    if (-not $found) { $updated += "$Name=$Value" }
    Set-Content -LiteralPath deployment.env -Value $updated -Encoding ASCII
}

Write-Host "Checking Docker Desktop..."
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Show-Failure "Docker Desktop is not installed. Install it from https://www.docker.com/products/docker-desktop/ and run Start.cmd again."
}
cmd.exe /d /c "docker info 1>nul 2>nul"
$dockerInfoExitCode = $LASTEXITCODE
if ($dockerInfoExitCode -ne 0) {
    Show-Failure "Docker Desktop is installed but not running. Open Docker Desktop, wait until it is ready, then run Start.cmd again."
}

$preferredOllamaPort = [int](Get-EnvValue "OLLAMA_PORT" "11434")
$preferredNgrokPort = [int](Get-EnvValue "NGROK_API_PORT" "4040")
$deploymentId = Get-EnvValue "DEPLOYMENT_ID" ""
$ollamaPort = $preferredOllamaPort
$ownOllamaContainer = cmd.exe /d /c "docker ps --filter name=$deploymentId-ollama --filter status=running --format {{.Names}} 2>nul"
if (-not $ownOllamaContainer -and -not (Test-PortAvailable $ollamaPort)) {
    $ollamaPort = Find-AvailablePort ($ollamaPort + 1)
}
$ngrokApiPort = $preferredNgrokPort
$ownNgrokContainer = cmd.exe /d /c "docker ps --filter name=$deploymentId-ngrok --filter status=running --format {{.Names}} 2>nul"
if (-not $ownNgrokContainer -and -not (Test-PortAvailable $ngrokApiPort)) {
    $ngrokApiPort = Find-AvailablePort ($ngrokApiPort + 1)
}
Set-EnvValue "OLLAMA_PORT" "$ollamaPort"
Set-EnvValue "NGROK_API_PORT" "$ngrokApiPort"
Write-Host "Using local Ollama port $ollamaPort and tunnel status port $ngrokApiPort."

Write-Host "Starting Ollama..."
docker compose --env-file deployment.env up -d ollama
if ($LASTEXITCODE -ne 0) { Show-Failure "Docker could not start Ollama." }

$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-RestMethod -Uri "http://127.0.0.1:$ollamaPort/api/tags" -TimeoutSec 2 | Out-Null; $ready = $true; break } catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) { Show-Failure "Ollama did not become ready within two minutes." }

$modelLine = Get-Content deployment.env | Where-Object { $_ -like "OLLAMA_MODEL=*" }
$model = $modelLine.Substring("OLLAMA_MODEL=".Length)
$installed = (Invoke-RestMethod -Uri "http://127.0.0.1:$ollamaPort/api/tags").models.name
if ($installed -notcontains $model) {
    Write-Host "Downloading model $model. This may take several minutes..."
    docker compose --env-file deployment.env --profile setup run --rm model-init
    if ($LASTEXITCODE -ne 0) { Show-Failure "The model download failed. Check your internet connection and available disk space, then run Start.cmd again." }
} else { Write-Host "Model already downloaded." }

Write-Host "Loading model into memory for faster first responses..."
try {
    $warmupBody = @{ model = $model; prompt = ""; stream = $false; keep_alive = "24h" } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$ollamaPort/api/generate" -ContentType "application/json" -Body $warmupBody -TimeoutSec 600 | Out-Null
} catch {
    Write-Host "The model could not be preloaded. It will load when the first request arrives." -ForegroundColor Yellow
}

Write-Host "Starting secure public tunnel..."
docker compose --env-file deployment.env up -d ngrok
if ($LASTEXITCODE -ne 0) { Show-Failure "Docker could not start the ngrok tunnel." }
$publicUrl = $null
for ($attempt = 0; $attempt -lt 2 -and -not $publicUrl; $attempt++) {
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:$ngrokApiPort/api/tunnels" -TimeoutSec 2
            $publicUrl = ($tunnels.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1).public_url
            if ($publicUrl) { break }
        } catch {}
        Start-Sleep -Seconds 2
    }
    if (-not $publicUrl -and $attempt -eq 0) { Write-Host "Tunnel did not connect; retrying once..."; docker compose --env-file deployment.env restart ngrok | Out-Null }
}

if (-not $publicUrl) {
    Write-Host ""
    Write-Host "The model is running locally at http://127.0.0.1:$ollamaPort" -ForegroundColor Green
    Write-Host "The public tunnel could not be created. Confirm that your ngrok connection key is valid, then run Start.cmd again." -ForegroundColor Yellow
    exit 2
}

$apiBaseUrl = "$($publicUrl.TrimEnd('/'))/v1"
try { Set-Clipboard -Value $apiBaseUrl } catch {}
Write-Host ""
Write-Host "Deployment ready" -ForegroundColor Green
Write-Host "Model: $model"
Write-Host "OpenAI-compatible API base URL: $apiBaseUrl" -ForegroundColor Cyan
Write-Host "The API base URL has been copied to your clipboard when clipboard access is available."
Write-Host "This URL is assigned by your ngrok account."
'''


def _stop_script() -> str:
    return r'''$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
docker compose --env-file deployment.env stop ngrok ollama
if ($LASTEXITCODE -ne 0) { Write-Host "The deployment could not be stopped." -ForegroundColor Red; exit 1 }
Write-Host "Deployment stopped. The downloaded model has been preserved." -ForegroundColor Green
'''


def _restart_script() -> str:
    return r'''$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
docker compose --env-file deployment.env stop ngrok ollama
if ($LASTEXITCODE -ne 0) { Write-Host "The deployment could not be stopped." -ForegroundColor Red; exit 1 }
& "$PSScriptRoot\start.ps1"
exit $LASTEXITCODE
'''


def _show_url_script() -> str:
    return r'''$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Get-EnvValue([string]$Name, [string]$DefaultValue) {
    $line = Get-Content deployment.env | Where-Object { $_ -like "$Name=*" } | Select-Object -First 1
    if ($line) { return $line.Substring($Name.Length + 1) }
    return $DefaultValue
}

$ngrokApiPort = [int](Get-EnvValue "NGROK_API_PORT" "4040")
try {
    $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:$ngrokApiPort/api/tunnels" -TimeoutSec 5
    $publicUrl = ($tunnels.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1).public_url
} catch {
    $publicUrl = $null
}

if (-not $publicUrl) {
    Write-Host "The public URL is not currently available." -ForegroundColor Yellow
    Write-Host "Run Start.cmd first and wait for the deployment to become ready."
    exit 1
}

$apiBaseUrl = "$($publicUrl.TrimEnd('/'))/v1"
try { Set-Clipboard -Value $apiBaseUrl } catch {}
Write-Host ""
Write-Host "OpenAI-compatible API base URL:" -ForegroundColor Green
Write-Host $apiBaseUrl -ForegroundColor Cyan
Write-Host ""
Write-Host "The API base URL has been copied to your clipboard when clipboard access is available."
'''


def _cmd(script: str) -> str:
    return f'''@echo off\r
cd /d "%~dp0"\r
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\{script}.ps1"\r
set EXIT_CODE=%ERRORLEVEL%\r
echo.\r
pause\r
exit /b %EXIT_CODE%\r
'''


def _build_zip(deployment_id: str, model: str, ngrok_authtoken: str) -> bytes:
    files = {
        "docker-compose.yml": _compose(),
        "deployment.env": f"DEPLOYMENT_ID={deployment_id}\nOLLAMA_MODEL={model}\nOLLAMA_PORT=11434\nNGROK_API_PORT=4040\nNGROK_AUTHTOKEN={ngrok_authtoken}\n",
        "Start.cmd": _cmd("start"),
        "Stop.cmd": _cmd("stop"),
        "Restart.cmd": _cmd("restart"),
        "Show URL.cmd": _cmd("show-url"),
        "scripts/start.ps1": _start_script(),
        "scripts/stop.ps1": _stop_script(),
        "scripts/restart.ps1": _restart_script(),
        "scripts/show-url.ps1": _show_url_script(),
        "README.txt": "Install and open Docker Desktop, then double-click Start.cmd. The selected model is preloaded and kept in memory for 24 hours after use. Use Show URL.cmd to display and copy the OpenAI-compatible API base URL again. Use Stop.cmd or Restart.cmd to manage the deployment. deployment.env contains your private ngrok connection key; do not share this folder or ZIP file.\n",
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


def generate_package(request: DeploymentRequest, base_url: str) -> DeploymentResponse:
    _validate(request)
    now = datetime.now(timezone.utc)
    _purge_expired_packages(now)
    deployment_id = f"dep_{uuid4().hex}"
    safe_tag = request.ollama_tag.replace("/", "-").replace(":", "-")
    filename = f"deploy-{safe_tag}-windows.zip"
    expires = now + timedelta(hours=1)
    PACKAGES[deployment_id] = DeploymentPackage(
        filename,
        _build_zip(deployment_id, request.ollama_tag, request.ngrok_authtoken.get_secret_value()),
        expires,
    )
    return DeploymentResponse(deploymentId=deployment_id, filename=filename, packageType=request.package_type,
        downloadUrl=f"{base_url.rstrip('/')}/api/deployments/{deployment_id}/download", expiresAt=expires.isoformat().replace("+00:00", "Z"))
