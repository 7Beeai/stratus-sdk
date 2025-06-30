"""
Search Result Validator para Stratus.IA
Responsável por validar e filtrar resultados de busca para garantir qualidade e confiabilidade
"""

import re
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse
from pydantic import BaseModel, Field

from .base import (
    SearchResult, 
    ContentType, 
    SourceReliability, 
    ValidationMetrics,
    ValidationStatus
)
from ..utils.logging import get_logger


class ValidationResult(BaseModel):
    """Resultado da validação de um resultado de busca"""
    search_result: SearchResult = Field(..., description="Resultado original")
    is_valid: bool = Field(..., description="Se o resultado é válido")
    validation_score: float = Field(..., description="Score de validação (0-1)")
    validation_status: ValidationStatus = Field(..., description="Status da validação")
    validation_errors: List[str] = Field(default_factory=list, description="Erros de validação")
    validation_warnings: List[str] = Field(default_factory=list, description="Avisos de validação")
    confidence_score: float = Field(..., description="Score de confiança (0-1)")
    duplicate_check: bool = Field(default=False, description="Se é duplicado")
    structured_data_valid: bool = Field(default=True, description="Se dados estruturados são válidos")
    validation_timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp da validação")


class ValidationConfig(BaseModel):
    """Configuração para validação"""
    min_relevance_score: float = Field(default=0.3, description="Score mínimo de relevância")
    min_authority_score: float = Field(default=0.4, description="Score mínimo de autoridade")
    min_freshness_score: float = Field(default=0.2, description="Score mínimo de atualidade")
    max_content_length: int = Field(default=50000, description="Tamanho máximo do conteúdo")
    min_content_length: int = Field(default=50, description="Tamanho mínimo do conteúdo")
    enable_duplicate_detection: bool = Field(default=True, description="Habilita detecção de duplicatas")
    enable_structured_validation: bool = Field(default=True, description="Habilita validação de dados estruturados")
    enable_source_verification: bool = Field(default=True, description="Habilita verificação de fonte")
    cache_ttl: timedelta = Field(default=timedelta(hours=24), description="TTL do cache de validação")


class StratusSearchValidator:
    """Validador especializado para resultados de busca de aviação"""
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()
        self.logger = get_logger()
        self.metrics = ValidationMetrics()
        
        # Cache de validação
        self.validation_cache: Dict[str, Dict[str, Any]] = {}
        
        # Cache de conteúdo para detecção de duplicatas
        self.content_hashes: Dict[str, str] = {}
        
        # Padrões de validação específicos para aviação
        self.validation_patterns = {
            ContentType.METAR_TAF: {
                'required_fields': ['icao_codes', 'times'],
                'metar_pattern': r'METAR\s+[A-Z]{4}\s+\d{6}Z',
                'taf_pattern': r'TAF\s+[A-Z]{4}\s+\d{6}Z',
                'icao_pattern': r'\b[A-Z]{4}\b',
                'time_pattern': r'\d{6}Z',
            },
            ContentType.NOTAM: {
                'required_fields': ['notam_id', 'icao_codes'],
                'notam_id_pattern': r'[A-Z]\d{4}/\d{2}',
                'icao_pattern': r'\b[A-Z]{4}\b',
                'coordinates_pattern': r'\d{1,2}°\d{1,2}\'[NS]\s+\d{1,3}°\d{1,2}\'[EW]',
            },
            ContentType.REGULATION: {
                'required_fields': ['rbac', 'ica'],
                'rbac_pattern': r'RBAC\s+\d+[A-Z]?',
                'ica_pattern': r'ICA\s+\d+[A-Z]?',
                'portaria_pattern': r'Portaria\s+\d+/\d+',
            },
            ContentType.EMERGENCY: {
                'required_fields': ['emergency_keywords'],
                'mayday_pattern': r'MAYDAY|MAYDAY|MAYDAY',
                'pan_pan_pattern': r'PAN\s+PAN|PAN\s+PAN',
                'emergency_pattern': r'EMERGENCY|EMERGÊNCIA',
            }
        }
        
        # Palavras-chave suspeitas
        self.suspicious_keywords = [
            'spam', 'clickbait', 'fake', 'hoax', 'scam', 'phishing',
            'malware', 'virus', 'hack', 'crack', 'pirate', 'illegal'
        ]
        
        # Domínios suspeitos
        self.suspicious_domains = [
            'spam.com', 'fake.com', 'scam.com', 'malware.com'
        ]
    
    async def validate_result(self, result: SearchResult) -> ValidationResult:
        """Valida um resultado de busca"""
        start_time = datetime.now()
        
        try:
            # Verifica cache
            cache_key = self._generate_cache_key(result)
            cached_validation = self._get_cached_validation(cache_key)
            if cached_validation:
                self.logger._log_info(f"Cache hit para validação: {result.url}")
                self.metrics.cache_hit_rate = self._update_cache_hit_rate(True)
                return cached_validation
            
            # Inicializa resultado de validação
            validation_result = ValidationResult(
                search_result=result,
                is_valid=True,
                validation_score=0.0,
                validation_status=ValidationStatus.PENDING,
                confidence_score=0.0
            )
            
            # Executa validações
            await self._validate_basic_requirements(result, validation_result)
            await self._validate_content_quality(result, validation_result)
            await self._validate_source_reliability(result, validation_result)
            await self._validate_structured_data(result, validation_result)
            await self._check_duplicates(result, validation_result)
            await self._validate_aviation_specific(result, validation_result)
            
            # Calcula scores finais
            self._calculate_final_scores(validation_result)
            
            # Atualiza cache
            self._cache_validation(cache_key, validation_result)
            
            # Atualiza métricas
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(True, execution_time, validation_result.is_valid)
            
            self.logger._log_info(
                f"Resultado validado: {result.title[:50]}...",
                url=result.url,
                title=result.title
            )
            
            return validation_result
            
        except Exception as e:
            self.logger._log_error(f"Erro na validação: {str(e)}")
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(False, execution_time, False)
            
            return ValidationResult(
                search_result=result,
                is_valid=False,
                validation_score=0.0,
                validation_status=ValidationStatus.FAILED,
                confidence_score=0.0,
                validation_errors=[f"Erro na validação: {str(e)}"]
            )
    
    async def validate_multiple_results(
        self, 
        results: List[SearchResult],
        filter_invalid: bool = True
    ) -> List[ValidationResult]:
        """Valida múltiplos resultados de busca"""
        validation_results = []
        
        for result in results:
            validation_result = await self.validate_result(result)
            validation_results.append(validation_result)
        
        # Filtra resultados inválidos se solicitado
        if filter_invalid:
            validation_results = [vr for vr in validation_results if vr.is_valid]
        
        return validation_results
    
    async def _validate_basic_requirements(
        self, 
        result: SearchResult, 
        validation_result: ValidationResult
    ):
        """Valida requisitos básicos"""
        
        # Verifica URL
        if not result.url or not self._is_valid_url(result.url):
            validation_result.validation_errors.append("URL inválida")
            validation_result.is_valid = False
        
        # Verifica título
        if not result.title or len(result.title.strip()) < 5:
            validation_result.validation_errors.append("Título muito curto ou vazio")
            validation_result.is_valid = False
        
        # Verifica snippet
        if not result.snippet or len(result.snippet.strip()) < 10:
            validation_result.validation_warnings.append("Snippet muito curto")
        
        # Verifica tamanho do conteúdo
        if result.content:
            content_length = len(result.content)
            if content_length < self.config.min_content_length:
                validation_result.validation_errors.append(f"Conteúdo muito curto: {content_length} caracteres")
                validation_result.is_valid = False
            elif content_length > self.config.max_content_length:
                validation_result.validation_warnings.append(f"Conteúdo muito longo: {content_length} caracteres")
    
    async def _validate_content_quality(
        self, 
        result: SearchResult, 
        validation_result: ValidationResult
    ):
        """Valida qualidade do conteúdo"""
        
        text = (result.title + " " + result.snippet).lower()
        
        # Verifica palavras-chave suspeitas
        suspicious_found = [kw for kw in self.suspicious_keywords if kw in text]
        if suspicious_found:
            validation_result.validation_errors.append(f"Palavras-chave suspeitas: {suspicious_found}")
            validation_result.is_valid = False
        
        # Verifica repetição excessiva
        words = text.split()
        if len(words) > 10:
            word_freq = {}
            for word in words:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            max_freq = max(word_freq.values())
            if max_freq > len(words) * 0.3:  # Mais de 30% de repetição
                validation_result.validation_warnings.append("Repetição excessiva de palavras")
        
        # Verifica scores mínimos
        if result.relevance_score < self.config.min_relevance_score:
            validation_result.validation_errors.append(f"Score de relevância muito baixo: {result.relevance_score}")
            validation_result.is_valid = False
        
        if result.authority_score < self.config.min_authority_score:
            validation_result.validation_errors.append(f"Score de autoridade muito baixo: {result.authority_score}")
            validation_result.is_valid = False
        
        if result.freshness_score < self.config.min_freshness_score:
            validation_result.validation_warnings.append(f"Score de atualidade baixo: {result.freshness_score}")
    
    async def _validate_source_reliability(
        self, 
        result: SearchResult, 
        validation_result: ValidationResult
    ):
        """Valida confiabilidade da fonte"""
        
        if not self.config.enable_source_verification:
            return
        
        # Verifica domínio suspeito
        domain = urlparse(result.url).netloc.lower()
        if any(suspicious in domain for suspicious in self.suspicious_domains):
            validation_result.validation_errors.append("Domínio suspeito")
            validation_result.is_valid = False
        
        # Verifica confiabilidade da fonte
        if result.source_reliability == SourceReliability.UNRELIABLE:
            validation_result.validation_errors.append("Fonte não confiável")
            validation_result.is_valid = False
        elif result.source_reliability == SourceReliability.QUESTIONABLE:
            validation_result.validation_warnings.append("Fonte questionável")
    
    async def _validate_structured_data(
        self, 
        result: SearchResult, 
        validation_result: ValidationResult
    ):
        """Valida dados estruturados"""
        
        if not self.config.enable_structured_validation:
            return
        
        if not result.extracted_data:
            validation_result.validation_warnings.append("Sem dados estruturados")
            return
        
        # Valida dados baseado no tipo de conteúdo
        if result.content_type in self.validation_patterns:
            patterns = self.validation_patterns[result.content_type]
            required_fields = patterns.get('required_fields', [])
            
            missing_fields = []
            for field in required_fields:
                if field not in result.extracted_data or not result.extracted_data[field]:
                    missing_fields.append(field)
            
            if missing_fields:
                validation_result.validation_warnings.append(f"Campos obrigatórios ausentes: {missing_fields}")
        
        # Valida formato dos dados
        validation_result.structured_data_valid = self._validate_data_format(result.extracted_data, result.content_type)
        if not validation_result.structured_data_valid:
            validation_result.validation_warnings.append("Formato de dados estruturados inválido")
    
    async def _check_duplicates(
        self, 
        result: SearchResult, 
        validation_result: ValidationResult
    ):
        """Verifica duplicatas"""
        
        if not self.config.enable_duplicate_detection:
            return
        
        # Gera hash do conteúdo
        content_hash = self._generate_content_hash(result)
        
        if content_hash in self.content_hashes:
            validation_result.duplicate_check = True
            validation_result.validation_warnings.append("Conteúdo duplicado detectado")
        else:
            self.content_hashes[content_hash] = result.url
    
    async def _validate_aviation_specific(
        self, 
        result: SearchResult, 
        validation_result: ValidationResult
    ):
        """Validações específicas para aviação"""
        
        text = (result.title + " " + result.snippet).lower()
        
        # Verifica se contém termos de aviação
        aviation_terms = [
            'metar', 'taf', 'notam', 'rbac', 'ica', 'aeroporto', 'pista',
            'piloto', 'voo', 'aviação', 'aeronáutica', 'decea', 'anac'
        ]
        
        has_aviation_terms = any(term in text for term in aviation_terms)
        if not has_aviation_terms:
            validation_result.validation_warnings.append("Poucos termos relacionados à aviação")
        
        # Validações específicas por tipo de conteúdo
        if result.content_type in self.validation_patterns:
            patterns = self.validation_patterns[result.content_type]
            
            for pattern_name, pattern in patterns.items():
                if pattern_name.endswith('_pattern'):
                    if not re.search(pattern, text, re.IGNORECASE):
                        validation_result.validation_warnings.append(f"Padrão {pattern_name} não encontrado")
    
    def _calculate_final_scores(self, validation_result: ValidationResult):
        """Calcula scores finais de validação"""
        
        # Score base
        base_score = 0.5
        
        # Ajustes baseados em erros e avisos
        error_penalty = len(validation_result.validation_errors) * 0.2
        warning_penalty = len(validation_result.validation_warnings) * 0.05
        
        # Bônus para qualidade
        quality_bonus = 0.0
        if validation_result.search_result.relevance_score > 0.7:
            quality_bonus += 0.1
        if validation_result.search_result.authority_score > 0.8:
            quality_bonus += 0.1
        if validation_result.structured_data_valid:
            quality_bonus += 0.1
        if not validation_result.duplicate_check:
            quality_bonus += 0.05
        
        # Calcula score final
        validation_score = max(0.0, min(1.0, base_score - error_penalty - warning_penalty + quality_bonus))
        validation_result.validation_score = validation_score
        
        # Calcula score de confiança
        confidence_factors = [
            validation_result.search_result.relevance_score * 0.3,
            validation_result.search_result.authority_score * 0.3,
            validation_result.search_result.freshness_score * 0.2,
            validation_score * 0.2
        ]
        validation_result.confidence_score = sum(confidence_factors)
        
        # Define status final
        if validation_result.is_valid and validation_score > 0.7:
            validation_result.validation_status = ValidationStatus.VALID
        elif validation_result.is_valid and validation_score > 0.5:
            validation_result.validation_status = ValidationStatus.WARNING
        else:
            validation_result.validation_status = ValidationStatus.INVALID
    
    def _is_valid_url(self, url: str) -> bool:
        """Verifica se a URL é válida"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def _validate_data_format(self, data: Dict[str, Any], content_type: ContentType) -> bool:
        """Valida formato dos dados estruturados"""
        if not data:
            return True
        
        # Validações básicas
        for key, value in data.items():
            if not isinstance(key, str):
                return False
            if not isinstance(value, (str, list, dict, int, float)):
                return False
        
        return True
    
    def _generate_content_hash(self, result: SearchResult) -> str:
        """Gera hash do conteúdo para detecção de duplicatas"""
        content = f"{result.title}{result.snippet}{result.url}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _generate_cache_key(self, result: SearchResult) -> str:
        """Gera chave de cache para validação"""
        content = f"{result.url}{result.title}{result.snippet}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_cached_validation(self, cache_key: str) -> Optional[ValidationResult]:
        """Recupera validação do cache"""
        if cache_key in self.validation_cache:
            cached_data = self.validation_cache[cache_key]
            
            # Verifica se não expirou
            if datetime.now() - cached_data['timestamp'] < self.config.cache_ttl:
                return cached_data['validation']
            else:
                # Remove entrada expirada
                del self.validation_cache[cache_key]
        
        return None
    
    def _cache_validation(self, cache_key: str, validation: ValidationResult):
        """Armazena validação no cache"""
        self.validation_cache[cache_key] = {
            'validation': validation,
            'timestamp': datetime.now()
        }
        
        # Limita tamanho do cache
        if len(self.validation_cache) > 1000:
            # Remove entradas mais antigas
            oldest_key = min(
                self.validation_cache.keys(),
                key=lambda k: self.validation_cache[k]['timestamp']
            )
            del self.validation_cache[oldest_key]
    
    def _update_metrics(self, success: bool, execution_time: float, is_valid: bool):
        """Atualiza métricas do validador"""
        self.metrics.total_validations += 1
        
        if success:
            self.metrics.successful_validations += 1
        else:
            self.metrics.failed_validations += 1
        
        if is_valid:
            self.metrics.valid_results += 1
        else:
            self.metrics.invalid_results += 1
        
        # Atualiza média de tempo de execução
        if self.metrics.avg_execution_time == 0:
            self.metrics.avg_execution_time = execution_time
        else:
            total_time = self.metrics.avg_execution_time * (self.metrics.total_validations - 1) + execution_time
            self.metrics.avg_execution_time = total_time / self.metrics.total_validations
        
        self.metrics.last_validation = datetime.now()
    
    def _update_cache_hit_rate(self, cache_hit: bool) -> float:
        """Atualiza taxa de cache hit"""
        if cache_hit:
            return min(self.metrics.cache_hit_rate + 0.01, 1.0)
        else:
            return max(self.metrics.cache_hit_rate - 0.01, 0.0)
    
    def get_metrics(self) -> ValidationMetrics:
        """Retorna métricas atuais do validador"""
        return self.metrics
    
    def clear_cache(self):
        """Limpa o cache de validação"""
        self.validation_cache.clear()
        self.content_hashes.clear()
        self.logger._log_info("Cache de validação limpo") 