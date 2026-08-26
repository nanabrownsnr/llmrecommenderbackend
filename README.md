# Ollama Model Deployment API

Scaffold for an API with two workflows:

1. Recommend locally runnable models from hardware specifications.
2. Generate a platform-specific installer package that installs Ollama, pulls and starts a model, and exposes it through a tunnel.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
uvicorn app.main:app --reload
```

Open the interactive API documentation at <http://127.0.0.1:8000/docs>.

## Endpoints

- `GET /health`
- `POST /api/recommendations`
- `POST /api/deployments`
- `GET /api/deployments/{deploymentId}/download`

Recommendation responses include only model variants scoring at least 70 for the corresponding use case. A model family is omitted from a use-case list when none of its variants meet that threshold. Each returned model family contains at most three variants: the highest-scoring recommendation and up to two alternatives.

Recommendation capacity defaults to 30% of detected system memory when `memoryUtilization` is omitted. An explicitly supplied value still controls the calculation. Missing or unavailable memory detection safely defaults to 8 GB.

The deployment endpoint generates platform-specific Docker Compose ZIPs for Windows, macOS, and Linux. It starts Ollama, pulls and preloads the selected model, keeps it warm for 24 hours after use, and exposes it through the free development domain associated with the supplied ngrok authtoken. Start and Show URL display and copy the OpenAI-compatible base URL ending in `/v1`. Docker and Docker Compose must already be installed and running.

`POST /api/deployments` requires `ngrokAuthtoken`. The generated ZIP contains this secret in `deployment.env`, expires from the API after one hour, and should not be shared.

## Production configuration

- Run one API process and one replica in v1 because downloadable packages are held in process memory for one hour.
- Set `PUBLIC_BASE_URL` to the API's public HTTPS origin, without a trailing slash.
- `CORS_ORIGINS` defaults to `*` for prototype frontend testing. Set it to a comma-separated list of frontend origins before production use.
- API 2 accepts the frontend's detected architecture but selects the v1 package by platform; Docker resolves the compatible container architecture. The macOS Docker package is CPU-only because Docker Desktop does not expose Apple Metal acceleration to Ollama containers.

## Render deployment

The repository includes a Dockerfile and `render.yaml`. Create a Render Blueprint from this repository, keep one instance, and use `/health` as the health-check path. Render supplies `PORT`, which the container reads automatically. After Render assigns the service URL, set `PUBLIC_BASE_URL` to that HTTPS origin and replace the prototype `CORS_ORIGINS=*` value with the frontend's origin when it is known.

API 1 uses the vendored LLM Checker SQLite snapshot at `vendor/llm-checker/src/data/seed/models.db`. Set `LLM_CHECKER_DB_PATH` only when using a different snapshot.

## Tests

```powershell
pytest
```
