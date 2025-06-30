from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class SearchDomain(Enum):
    AVIATION_OFFICIAL = "aviation_official"
    METEOROLOGY = "meteorology"
    REGULATIONS = "regulations"
    NOTAMS = "notams"
    AIRPORTS = "airports"
    GENERAL_AVIATION = "general_aviation"
    EMERGENCY = "emergency"

class ContentType(Enum):
    METAR_TAF = "metar_taf"
    NOTAM = "notam"
    REGULATION = "regulation"
    NEWS = "news"
    TECHNICAL = "technical"
    EMERGENCY = "emergency"
    GENERAL = "general"

class SourceReliability(Enum):
    OFFICIAL = "official"
    VERIFIED = "verified"
    RELIABLE = "reliable"
    QUESTIONABLE = "questionable"
    UNRELIABLE = "unreliable"

class ScrapingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"

class ValidationStatus(Enum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"
    FAILED = "failed"

class UpdateStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class SearchQuery(BaseModel):
    """Query de busca estruturada"""
    original_query: str = Field(description="Query original do usuário")
    processed_query: str = Field(description="Query processada e otimizada")
    domain: SearchDomain = Field(description="Domínio da busca")
    keywords: List[str] = Field(description="Palavras-chave extraídas")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Filtros aplicados")
    priority: int = Field(ge=1, le=10, description="Prioridade da busca (1=baixa, 10=crítica)")

class SearchResult(BaseModel):
    """Resultado individual de busca"""
    url: str = Field(description="URL do resultado")
    title: str = Field(description="Título da página")
    snippet: str = Field(description="Snippet/resumo do conteúdo")
    content: Optional[str] = Field(None, description="Conteúdo completo extraído")
    source_reliability: SourceReliability = Field(description="Confiabilidade da fonte")
    content_type: ContentType = Field(description="Tipo de conteúdo")
    relevance_score: float = Field(ge=0.0, le=1.0, description="Score de relevância")
    freshness_score: float = Field(ge=0.0, le=1.0, description="Score de atualidade")
    authority_score: float = Field(ge=0.0, le=1.0, description="Score de autoridade")
    extracted_data: Dict[str, Any] = Field(default_factory=dict, description="Dados estruturados extraídos")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp da busca")

class ValidationResult(BaseModel):
    """Resultado da validação de conteúdo"""
    is_valid: bool = Field(description="Se o resultado é válido")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confiança na validação")
    validation_issues: List[str] = Field(default_factory=list, description="Problemas identificados")
    content_quality: float = Field(ge=0.0, le=1.0, description="Qualidade do conteúdo")
    source_authority: float = Field(ge=0.0, le=1.0, description="Autoridade da fonte")
    factual_accuracy: float = Field(ge=0.0, le=1.0, description="Precisão factual estimada")
    reasoning: str = Field(description="Raciocínio da validação")

class KnowledgeUpdate(BaseModel):
    """Atualização de conhecimento"""
    topic: str = Field(description="Tópico atualizado")
    old_information: Optional[str] = Field(None, description="Informação anterior")
    new_information: str = Field(description="Nova informação")
    source_url: str = Field(description="URL da fonte")
    confidence: float = Field(ge=0.0, le=1.0, description="Confiança na atualização")
    update_type: str = Field(description="Tipo de atualização (new, update, correction)")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp da atualização")

@dataclass
class SearchMetrics:
    """Métricas do sistema de busca"""
    total_searches: int = 0
    successful_searches: int = 0
    failed_searches: int = 0
    avg_response_time: float = 0.0
    avg_results_per_search: float = 0.0
    cache_hit_rate: float = 0.0
    last_search: Optional[datetime] = None

@dataclass
class ScrapingMetrics:
    """Métricas do sistema de scraping"""
    total_scrapes: int = 0
    successful_scrapes: int = 0
    failed_scrapes: int = 0
    avg_execution_time: float = 0.0
    avg_content_length: int = 0
    cache_hit_rate: float = 0.0
    last_scrape: Optional[datetime] = None

@dataclass
class ValidationMetrics:
    """Métricas do sistema de validação"""
    total_validations: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    valid_results: int = 0
    invalid_results: int = 0
    avg_execution_time: float = 0.0
    cache_hit_rate: float = 0.0
    last_validation: Optional[datetime] = None

@dataclass
class UpdateMetrics:
    """Métricas do sistema de atualização"""
    total_updates: int = 0
    successful_updates: int = 0
    failed_updates: int = 0
    success_rate: float = 0.0
    avg_execution_time: float = 0.0
    last_update: Optional[datetime] = None

# Alias para compatibilidade
WebSearchMetrics = SearchMetrics 