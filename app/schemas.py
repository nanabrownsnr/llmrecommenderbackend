from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, SecretStr

class UseCase(str, Enum):
    all = "all"
    chat = "chat"
    coding = "coding"
    reasoning = "reasoning"
    writing = "writing"
    fast = "fast"

class Cpu(BaseModel):
    logical_threads: int = Field(..., alias="logicalThreads", ge=1)
    model: str
    model_config = ConfigDict(populate_by_name=True)

class Memory(BaseModel):
    approximate_gb: float = Field(..., alias="approximateGB", gt=0)
    model_config = ConfigDict(populate_by_name=True)

class System(BaseModel):
    platform: str
    architecture: str
    bitness: str

class Gpu(BaseModel):
    status: str
    confidence: str
    renderer: str

class Hardware(BaseModel):
    cpu: Cpu
    memory: Memory
    system: System
    gpu: Gpu

class RecommendationRequest(BaseModel):
    hardware: Hardware
    use_case: UseCase = Field(UseCase.all, alias="useCase")
    memory_utilization: float = Field(0.5, alias="memoryUtilization", gt=0, le=1)
    limit: int = Field(20, ge=1, le=100)
    cursor: str | None = None
    model_config = ConfigDict(populate_by_name=True)

class Recommendation(BaseModel):
    model_id: str = Field(alias="modelId")
    name: str
    ollama_tag: str = Field(alias="ollamaTag")
    size_gb: float = Field(alias="sizeGB")
    estimated_runtime_gb: float = Field(alias="estimatedRuntimeGB")
    fit: str
    use_cases: list[str] = Field(alias="useCases")
    description: str
    model_config = ConfigDict(populate_by_name=True)

class RecommendedVariant(BaseModel):
    ollama_tag: str = Field(alias="ollamaTag")
    size_gb: float = Field(alias="sizeGB")
    estimated_runtime_gb: float = Field(alias="estimatedRuntimeGB")
    fit: str
    score: float
    model_config = ConfigDict(populate_by_name=True)

class ModelRecommendation(BaseModel):
    model_id: str = Field(alias="modelId")
    name: str
    description: str
    fit: str
    best_variant: RecommendedVariant = Field(alias="bestVariant")
    variants: list[RecommendedVariant]
    model_config = ConfigDict(populate_by_name=True)

class RecommendationResponse(BaseModel):
    recommendations: dict[str, list[ModelRecommendation]]
    next_cursors: dict[str, str | None] = Field(default_factory=dict, alias="nextCursors")
    model_config = ConfigDict(populate_by_name=True)

class DeploymentRequest(BaseModel):
    model_id: str = Field(alias="modelId", min_length=1)
    ollama_tag: str = Field(alias="ollamaTag", min_length=1)
    platform: str
    architecture: str = Field(min_length=1)
    package_type: str = Field("docker-compose", alias="packageType")
    enable_tunnel: bool = Field(True, alias="enableTunnel")
    ngrok_authtoken: SecretStr = Field(alias="ngrokAuthtoken")
    model_config = ConfigDict(populate_by_name=True)

class DeploymentResponse(BaseModel):
    deployment_id: str = Field(alias="deploymentId")
    filename: str
    package_type: str = Field(alias="packageType")
    download_url: str = Field(alias="downloadUrl")
    expires_at: str = Field(alias="expiresAt")
    model_config = ConfigDict(populate_by_name=True)
