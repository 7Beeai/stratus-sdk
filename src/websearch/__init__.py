"""
Sistema de Websearch para Stratus.IA
Módulo completo para busca, extração, validação e atualização de conhecimento aeronáutico
"""

from .base import (
    # Enums
    SearchDomain,
    ContentType,
    SourceReliability,
    ScrapingStatus,
    ValidationStatus,
    UpdateStatus,
    
    # Modelos
    SearchQuery,
    SearchResult,
    SearchMetrics,
    ScrapingMetrics,
    ValidationMetrics,
    UpdateMetrics,
)

from .engine import StratusWebSearchEngine
from .scraper import StratusContentScraper, ScrapedContent, ScrapingConfig
from .validator import StratusSearchValidator, ValidationResult, ValidationConfig
from .updater import StratusKnowledgeUpdater, KnowledgeUpdate, UpdateConfig

__all__ = [
    # Enums
    'SearchDomain',
    'ContentType', 
    'SourceReliability',
    'ScrapingStatus',
    'ValidationStatus',
    'UpdateStatus',
    
    # Modelos base
    'SearchQuery',
    'SearchResult',
    'SearchMetrics',
    'ScrapingMetrics',
    'ValidationMetrics',
    'UpdateMetrics',
    
    # Componentes principais
    'StratusWebSearchEngine',
    'StratusContentScraper',
    'StratusSearchValidator',
    'StratusKnowledgeUpdater',
    
    # Modelos específicos
    'ScrapedContent',
    'ScrapingConfig',
    'ValidationResult',
    'ValidationConfig',
    'KnowledgeUpdate',
    'UpdateConfig',
]

__version__ = "1.0.0"
__author__ = "Stratus.IA Team"
__description__ = "Sistema completo de websearch especializado para aviação civil brasileira" 