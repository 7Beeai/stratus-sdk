"""
Stratus.IA - Configurações Centralizadas
Sistema de IA para Aviação Civil Brasileira

Este módulo gerencia todas as configurações do sistema, incluindo:
- Variáveis de ambiente
- Google Cloud Secret Manager
- Validação de configurações obrigatórias
- Configurações específicas para aviação
"""

import os
import logging
from typing import Optional, Dict, Any, List
from enum import Enum
from functools import lru_cache

try:
    from google.cloud import secretmanager
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    secretmanager = None

from pydantic import Field, validator, root_validator, ConfigDict
from pydantic.types import SecretStr
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator


class Environment(str, Enum):
    """Ambientes disponíveis para o sistema."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Níveis de log disponíveis."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """
    Configurações centralizadas do Stratus.IA.
    
    Suporta carregamento de variáveis de ambiente e Google Cloud Secret Manager.
    """
    
    # =============================================================================
    # CONFIGURAÇÕES BÁSICAS
    # =============================================================================
    
    # Ambiente de execução
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Ambiente de execução (development/staging/production)",
        json_schema_extra={"env": "ENVIRONMENT"}
    )
    
    # Configurações de logging
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Nível de log do sistema",
        json_schema_extra={"env": "LOG_LEVEL"}
    )
    
    log_format: str = Field(
        default="json",
        description="Formato dos logs (json/text)",
        json_schema_extra={"env": "LOG_FORMAT"}
    )
    
    enable_structured_logging: bool = Field(
        default=True,
        description="Habilitar logging estruturado",
        json_schema_extra={"env": "ENABLE_STRUCTURED_LOGGING"}
    )
    
    # =============================================================================
    # OPENAI CONFIGURAÇÕES
    # =============================================================================
    
    openai_api_key: SecretStr = Field(
        ...,
        description="Chave da API OpenAI",
        json_schema_extra={"env": "OPENAI_API_KEY"}
    )
    
    openai_model: str = Field(
        description="Modelo OpenAI para agentes",
        default="gpt-4.1",
        json_schema_extra={"env": "OPENAI_MODEL"}
    )
    
    openai_max_tokens: int | None = Field(
        description="Máximo de tokens por requisição (opcional)",
        default=None,
        json_schema_extra={"env": "OPENAI_MAX_TOKENS"}
    )
    
    openai_temperature: float = Field(
        default=0.1,
        description="Temperatura para geração de respostas (0.0-1.0)",
        json_schema_extra={"env": "OPENAI_TEMPERATURE"}
    )
    
    # =============================================================================
    # PINECONE CONFIGURAÇÕES
    # =============================================================================
    
    pinecone_api_key: SecretStr = Field(
        ...,  # Obrigatório
        description="Chave da API Pinecone",
        json_schema_extra={"env": "PINECONE_API_KEY"}
    )
    
    pinecone_environment: str = Field(
        ...,  # Obrigatório
        description="Ambiente Pinecone (ex: us-east1-gcp)",
        json_schema_extra={"env": "PINECONE_ENVIRONMENT"}
    )
    
    pinecone_index_name: str = Field(
        default="stratus-ia-aviation",
        description="Nome do índice Pinecone",
        json_schema_extra={"env": "PINECONE_INDEX_NAME"}
    )
    
    pinecone_dimension: int = Field(
        default=1536,
        description="Dimensão dos vetores Pinecone",
        json_schema_extra={"env": "PINECONE_DIMENSION"}
    )
    
    # =============================================================================
    # DATABASE CONFIGURAÇÕES
    # =============================================================================
    
    database_url: SecretStr = Field(
        default="sqlite:///./stratus_ia.db",
        description="URL de conexão com o banco de dados",
        json_schema_extra={"env": "DATABASE_URL"}
    )
    
    database_pool_size: int = Field(
        default=10,
        description="Tamanho do pool de conexões",
        json_schema_extra={"env": "DATABASE_POOL_SIZE"}
    )
    
    database_max_overflow: int = Field(
        default=20,
        description="Máximo de conexões overflow",
        json_schema_extra={"env": "DATABASE_MAX_OVERFLOW"}
    )
    
    # =============================================================================
    # GOOGLE CLOUD CONFIGURAÇÕES
    # =============================================================================
    
    google_cloud_project: Optional[str] = Field(
        default=None,
        description="ID do projeto Google Cloud",
        json_schema_extra={"env": "GOOGLE_CLOUD_PROJECT"}
    )
    
    google_cloud_region: str = Field(
        default="us-central1",
        description="Região do Google Cloud",
        json_schema_extra={"env": "GOOGLE_CLOUD_REGION"}
    )
    
    use_google_secret_manager: bool = Field(
        default=False,
        description="Usar Google Secret Manager para secrets",
        json_schema_extra={"env": "USE_GOOGLE_SECRET_MANAGER"}
    )
    
    # =============================================================================
    # PERFORMANCE E RESILIÊNCIA
    # =============================================================================
    
    max_retries: int = Field(
        default=3,
        description="Número máximo de tentativas para operações",
        json_schema_extra={"env": "MAX_RETRIES"}
    )
    
    timeout_seconds: float = Field(
        default=30.0,
        description="Timeout padrão em segundos",
        json_schema_extra={"env": "TIMEOUT_SECONDS"}
    )
    
    cache_ttl_seconds: int = Field(
        default=3600,
        description="TTL do cache em segundos",
        json_schema_extra={"env": "CACHE_TTL_SECONDS"}
    )
    
    max_response_time: float = Field(
        default=2.0,
        description="Tempo máximo de resposta em segundos (SLA crítico)",
        json_schema_extra={"env": "MAX_RESPONSE_TIME"}
    )
    
    # =============================================================================
    # REDIS CONFIGURAÇÕES
    # =============================================================================
    
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="URL de conexão com Redis",
        json_schema_extra={"env": "REDIS_URL"}
    )
    
    redis_password: Optional[SecretStr] = Field(
        default=None,
        description="Senha do Redis",
        json_schema_extra={"env": "REDIS_PASSWORD"}
    )
    
    redis_db: int = Field(
        default=0,
        description="Número do banco Redis",
        json_schema_extra={"env": "REDIS_DB"}
    )
    
    # =============================================================================
    # API CONFIGURAÇÕES
    # =============================================================================
    
    api_host: str = Field(
        default="0.0.0.0",
        description="Host da API FastAPI",
        json_schema_extra={"env": "API_HOST"}
    )
    
    api_port: int = Field(
        default=8000,
        description="Porta da API FastAPI",
        json_schema_extra={"env": "API_PORT"}
    )
    
    api_workers: int = Field(
        default=4,
        description="Número de workers da API",
        json_schema_extra={"env": "API_WORKERS"}
    )
    
    enable_cors: bool = Field(
        default=True,
        description="Habilitar CORS",
        json_schema_extra={"env": "ENABLE_CORS"}
    )
    
    cors_origins: List[str] = Field(
        default=["http://localhost:3000"],
        description="Origens permitidas para CORS",
        json_schema_extra={"env": "CORS_ORIGINS"}
    )
    
    # =============================================================================
    # SEGURANÇA E GUARDRAILS
    # =============================================================================
    
    enable_aviation_guardrails: bool = Field(
        default=True,
        description="Habilitar guardrails específicos para aviação",
        json_schema_extra={"env": "ENABLE_AVIATION_GUARDRAILS"}
    )
    
    icao_code_validation: bool = Field(
        default=True,
        description="Validar códigos ICAO",
        json_schema_extra={"env": "ICAO_CODE_VALIDATION"}
    )
    
    rbac_enforcement: bool = Field(
        default=True,
        description="Aplicar controle de acesso baseado em função",
        json_schema_extra={"env": "RBAC_ENFORCEMENT"}
    )
    
    # =============================================================================
    # MCP SERVERS CONFIGURAÇÕES
    # =============================================================================
    
    # REDEMET
    redemet_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Chave da API REDEMET",
        json_schema_extra={"env": "REDEMET_API_KEY"}
    )
    
    redemet_base_url: str = Field(
        default="https://api.redemet.aer.mil.br",
        description="URL base da API REDEMET",
        json_schema_extra={"env": "REDEMET_BASE_URL"}
    )
    
    # AISWEB
    aisweb_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Chave da API AISWEB",
        json_schema_extra={"env": "AISWEB_API_KEY"}
    )
    
    aisweb_base_url: str = Field(
        default="https://aisweb.decea.gov.br/api",
        description="URL base da API AISWEB",
        json_schema_extra={"env": "AISWEB_BASE_URL"}
    )
    
    # Weather APIs
    weather_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Chave da API Weather",
        json_schema_extra={"env": "WEATHER_API_KEY"}
    )
    
    weather_base_url: str = Field(
        default="https://api.weatherapi.com/v1",
        description="URL base da API Weather",
        json_schema_extra={"env": "WEATHER_BASE_URL"}
    )
    
    # =============================================================================
    # VALIDATORS
    # =============================================================================
    
    @field_validator("openai_temperature")
    @classmethod
    def validate_openai_temperature(cls, v):
        """Validar temperatura do OpenAI."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Temperatura deve estar entre 0.0 e 1.0")
        return v
    
    @field_validator("max_response_time")
    @classmethod
    def validate_max_response_time(cls, v):
        """Validar tempo máximo de resposta (SLA crítico)."""
        if v <= 0:
            raise ValueError("Tempo máximo de resposta deve ser positivo")
        if v > 10.0:
            raise ValueError("Tempo máximo de resposta não pode exceder 10 segundos")
        return v
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins de string para lista."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @model_validator(mode="after")
    def validate_google_cloud_config(self):
        """Validar configurações do Google Cloud."""
        if self.use_google_secret_manager and not self.google_cloud_project:
            raise ValueError("google_cloud_project é obrigatório quando use_google_secret_manager=True")
        return self
    
    # =============================================================================
    # MÉTODOS AUXILIARES
    # =============================================================================
    
    def is_production(self) -> bool:
        """Verificar se está em produção."""
        return self.environment == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        """Verificar se está em desenvolvimento."""
        return self.environment == Environment.DEVELOPMENT
    
    def is_staging(self) -> bool:
        """Verificar se está em staging."""
        return self.environment == Environment.STAGING
    
    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Obter secret do Google Secret Manager ou variável de ambiente.
        
        Args:
            secret_name: Nome do secret
            
        Returns:
            Valor do secret ou None se não encontrado
        """
        if self.use_google_secret_manager and GOOGLE_CLOUD_AVAILABLE:
            try:
                client = secretmanager.SecretManagerServiceClient()
                name = f"projects/{self.google_cloud_project}/secrets/{secret_name}/versions/latest"
                response = client.access_secret_version(request={"name": name})
                return response.payload.data.decode("UTF-8")
            except Exception as e:
                logging.warning(f"Erro ao acessar secret {secret_name}: {e}")
                return None
        
        # Fallback para variável de ambiente
        return os.getenv(secret_name)
    
    def get_database_url(self) -> str:
        """Obter URL do banco de dados com fallback para SQLite."""
        if self.database_url:
            return self.database_url.get_secret_value()
        return "sqlite:///./stratus_ia.db"
    
    def get_redis_url(self) -> str:
        """Obter URL do Redis com autenticação."""
        if self.redis_password:
            # Inserir senha na URL do Redis
            if "://" in self.redis_url:
                base_url = self.redis_url.split("://")[1]
                return f"redis://:{self.redis_password.get_secret_value()}@{base_url}"
        return self.redis_url
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# =============================================================================
# INSTÂNCIA GLOBAL
# =============================================================================

@lru_cache()
def get_settings() -> Settings:
    """
    Obter instância singleton das configurações.
    
    Returns:
        Instância das configurações
    """
    return Settings()


# Instância global para uso em outros módulos
settings = get_settings()


# =============================================================================
# VALIDAÇÃO INICIAL
# =============================================================================

def validate_critical_settings():
    """
    Validar configurações críticas na inicialização.
    
    Raises:
        ValueError: Se configurações críticas estiverem inválidas
    """
    try:
        # Verificar se as configurações obrigatórias estão presentes
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY é obrigatória")
        
        if not settings.pinecone_api_key:
            raise ValueError("PINECONE_API_KEY é obrigatória")
        
        if not settings.pinecone_environment:
            raise ValueError("PINECONE_ENVIRONMENT é obrigatório")
        
        # Log das configurações carregadas
        logging.info(f"Configurações carregadas para ambiente: {settings.environment}")
        logging.info(f"Log level: {settings.log_level}")
        logging.info(f"Max response time: {settings.max_response_time}s")
        
    except Exception as e:
        logging.error(f"Erro ao validar configurações: {e}")
        raise


# Executar validação na importação do módulo
if __name__ != "__main__":
    validate_critical_settings() 