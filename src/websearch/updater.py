"""
Knowledge Updater para Stratus.IA
Responsável por atualizar automaticamente o conhecimento baseado em novos dados de busca
"""

import asyncio
import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlparse
from pydantic import BaseModel, Field

from .base import (
    SearchResult, 
    ContentType, 
    SourceReliability, 
    UpdateMetrics,
    UpdateStatus
)
from ..utils.logging import get_logger


class KnowledgeUpdate(BaseModel):
    """Atualização de conhecimento"""
    id: str = Field(..., description="ID único da atualização")
    source_url: str = Field(..., description="URL da fonte")
    content_type: ContentType = Field(..., description="Tipo de conteúdo")
    content_hash: str = Field(..., description="Hash do conteúdo")
    update_data: Dict[str, Any] = Field(..., description="Dados da atualização")
    source_reliability: SourceReliability = Field(..., description="Confiabilidade da fonte")
    update_timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp da atualização")
    status: UpdateStatus = Field(default=UpdateStatus.PENDING, description="Status da atualização")
    priority: int = Field(default=5, description="Prioridade da atualização (1-10)")


class UpdateConfig(BaseModel):
    """Configuração para atualização de conhecimento"""
    enable_auto_update: bool = Field(default=True, description="Habilita atualização automática")
    update_interval: timedelta = Field(default=timedelta(hours=6), description="Intervalo entre atualizações")
    max_updates_per_batch: int = Field(default=100, description="Máximo de atualizações por lote")
    min_content_length: int = Field(default=100, description="Tamanho mínimo do conteúdo")
    enable_pinecone_integration: bool = Field(default=True, description="Habilita integração com Pinecone")
    enable_embedding_update: bool = Field(default=True, description="Habilita atualização de embeddings")
    cache_ttl: timedelta = Field(default=timedelta(days=7), description="TTL do cache de atualizações")


class StratusKnowledgeUpdater:
    """Atualizador de conhecimento especializado para aviação"""
    
    def __init__(self, config: Optional[UpdateConfig] = None):
        self.config = config or UpdateConfig()
        self.logger = get_logger()
        self.metrics = UpdateMetrics()
        
        # Cache de atualizações
        self.update_cache: Dict[str, Dict[str, Any]] = {}
        
        # Fila de atualizações pendentes
        self.pending_updates: List[KnowledgeUpdate] = []
        
        # Histórico de atualizações
        self.update_history: List[KnowledgeUpdate] = []
        
        # Mapeamento de tipos de conteúdo para prioridades
        self.content_priorities = {
            ContentType.EMERGENCY: 10,
            ContentType.NOTAM: 9,
            ContentType.METAR_TAF: 8,
            ContentType.REGULATION: 7,
            ContentType.TECHNICAL: 6,
            ContentType.NEWS: 5,
            ContentType.GENERAL: 4,
        }
        
        # Padrões de extração para diferentes tipos de conteúdo
        self.extraction_patterns = {
            ContentType.METAR_TAF: {
                'icao_codes': r'\b[A-Z]{4}\b',
                'metar_data': r'METAR\s+[A-Z]{4}\s+\d{6}Z\s+[A-Z0-9\s/]+',
                'taf_data': r'TAF\s+[A-Z]{4}\s+\d{6}Z\s+[A-Z0-9\s/]+',
                'weather_conditions': r'[A-Z]{2,3}',
                'visibility': r'\d{4}',
                'wind': r'\d{3}\d{2,3}KT',
            },
            ContentType.NOTAM: {
                'notam_id': r'[A-Z]\d{4}/\d{2}',
                'icao_codes': r'\b[A-Z]{4}\b',
                'coordinates': r'\d{1,2}°\d{1,2}\'[NS]\s+\d{1,3}°\d{1,2}\'[EW]',
                'radius': r'RADIUS\s+\d+\s+[A-Z]+',
                'altitude': r'[A-Z]+\s+\d+\s+[A-Z]+',
                'time_period': r'\d{6}\s+\d{6}',
            },
            ContentType.REGULATION: {
                'rbac_references': r'RBAC\s+\d+[A-Z]?',
                'ica_references': r'ICA\s+\d+[A-Z]?',
                'portaria_references': r'Portaria\s+\d+/\d+',
                'regulation_numbers': r'\d+/\d+',
            },
            ContentType.EMERGENCY: {
                'emergency_keywords': r'EMERGENCY|EMERGÊNCIA|MAYDAY|PAN\s+PAN',
                'incident_types': r'FALHA|FAILURE|MALFUNCTION|ACIDENTE',
                'priority_levels': r'CRÍTICO|CRITICAL|ALTO|HIGH',
            }
        }
    
    async def process_search_results(
        self, 
        results: List[SearchResult],
        force_update: bool = False
    ) -> List[KnowledgeUpdate]:
        """Processa resultados de busca para atualização de conhecimento"""
        updates = []
        
        for result in results:
            try:
                # Verifica se precisa atualizar
                if not force_update and not self._needs_update(result):
                    continue
                
                # Cria atualização de conhecimento
                update = await self._create_knowledge_update(result)
                if update:
                    updates.append(update)
                    self.pending_updates.append(update)
                
            except Exception as e:
                self.logger._log_error(f"Erro ao processar resultado: {str(e)}")
                continue
        
        # Ordena por prioridade
        updates.sort(key=lambda x: x.priority, reverse=True)
        
        self.logger._log_info(f"Processados {len(updates)} resultados para atualização")
        return updates
    
    async def execute_updates(
        self, 
        updates: Optional[List[KnowledgeUpdate]] = None,
        max_concurrent: int = 5
    ) -> List[KnowledgeUpdate]:
        """Executa atualizações de conhecimento"""
        if updates is None:
            updates = self.pending_updates.copy()
            self.pending_updates.clear()
        
        if not updates:
            return []
        
        # Limita número de atualizações por lote
        updates = updates[:self.config.max_updates_per_batch]
        
        # Executa atualizações em paralelo
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def execute_update(update: KnowledgeUpdate) -> KnowledgeUpdate:
            async with semaphore:
                return await self._execute_single_update(update)
        
        tasks = [execute_update(update) for update in updates]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Processa resultados
        successful_updates = []
        for result in results:
            if isinstance(result, KnowledgeUpdate):
                successful_updates.append(result)
                self.update_history.append(result)
            elif isinstance(result, Exception):
                self.logger._log_error(f"Erro na atualização: {str(result)}")
        
        # Atualiza métricas
        self._update_metrics(len(successful_updates), len(updates))
        
        self.logger._log_info(f"Executadas {len(successful_updates)} atualizações de conhecimento")
        return successful_updates
    
    async def _create_knowledge_update(self, result: SearchResult) -> Optional[KnowledgeUpdate]:
        """Cria uma atualização de conhecimento a partir de um resultado"""
        
        # Gera hash do conteúdo
        content_hash = self._generate_content_hash(result)
        
        # Verifica se já foi processado
        if self._is_already_processed(content_hash):
            return None
        
        # Extrai dados estruturados
        update_data = self._extract_update_data(result)
        
        # Determina prioridade
        priority = self._calculate_priority(result)
        
        # Cria ID único
        update_id = self._generate_update_id(result.url, content_hash)
        
        update = KnowledgeUpdate(
            id=update_id,
            source_url=result.url,
            content_type=result.content_type,
            content_hash=content_hash,
            update_data=update_data,
            source_reliability=result.source_reliability,
            priority=priority
        )
        
        return update
    
    async def _execute_single_update(self, update: KnowledgeUpdate) -> KnowledgeUpdate:
        """Executa uma única atualização"""
        start_time = datetime.now()
        
        try:
            # Atualiza status
            update.status = UpdateStatus.PROCESSING
            
            # Processa dados da atualização
            processed_data = await self._process_update_data(update)
            
            # Integra com Pinecone se habilitado
            if self.config.enable_pinecone_integration:
                await self._update_pinecone_knowledge(update, processed_data)
            
            # Atualiza embeddings se habilitado
            if self.config.enable_embedding_update:
                await self._update_embeddings(update, processed_data)
            
            # Marca como concluída
            update.status = UpdateStatus.COMPLETED
            update.update_timestamp = datetime.now()
            
            # Atualiza cache
            self._cache_update(update)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self.logger._log_info(
                f"Atualização concluída: {update.id} em {execution_time:.2f}s",
                extra={
                    "update_id": update.id,
                    "content_type": update.content_type.value,
                    "priority": update.priority
                }
            )
            
            return update
            
        except Exception as e:
            self.logger._log_error(f"Erro na atualização {update.id}: {str(e)}")
            update.status = UpdateStatus.FAILED
            return update
    
    def _needs_update(self, result: SearchResult) -> bool:
        """Verifica se um resultado precisa ser atualizado"""
        
        # Verifica tamanho mínimo
        if result.content and len(result.content) < self.config.min_content_length:
            return False
        
        # Verifica confiabilidade da fonte
        if result.source_reliability == SourceReliability.UNRELIABLE:
            return False
        
        # Verifica se é conteúdo recente
        # (implementação simplificada - em produção usaria data real)
        return True
    
    def _extract_update_data(self, result: SearchResult) -> Dict[str, Any]:
        """Extrai dados para atualização"""
        data = {
            'title': result.title,
            'snippet': result.snippet,
            'content': result.content,
            'url': result.url,
            'content_type': result.content_type.value,
            'source_reliability': result.source_reliability.value,
            'relevance_score': result.relevance_score,
            'authority_score': result.authority_score,
            'freshness_score': result.freshness_score,
            'extracted_data': result.extracted_data,
            'extraction_timestamp': datetime.now().isoformat(),
        }
        
        # Adiciona dados específicos do tipo de conteúdo
        if result.content_type in self.extraction_patterns:
            patterns = self.extraction_patterns[result.content_type]
            content_text = f"{result.title} {result.snippet} {result.content or ''}"
            
            for data_type, pattern in patterns.items():
                matches = re.findall(pattern, content_text, re.IGNORECASE)
                if matches:
                    data[f'extracted_{data_type}'] = matches
        
        return data
    
    def _calculate_priority(self, result: SearchResult) -> int:
        """Calcula prioridade da atualização"""
        base_priority = self.content_priorities.get(result.content_type, 5)
        
        # Ajusta baseado na confiabilidade da fonte
        reliability_bonus = {
            SourceReliability.OFFICIAL: 2,
            SourceReliability.VERIFIED: 1,
            SourceReliability.RELIABLE: 0,
            SourceReliability.QUESTIONABLE: -1,
            SourceReliability.UNRELIABLE: -2,
        }.get(result.source_reliability, 0)
        
        # Ajusta baseado nos scores
        score_bonus = 0
        if result.relevance_score > 0.8:
            score_bonus += 1
        if result.authority_score > 0.8:
            score_bonus += 1
        if result.freshness_score > 0.8:
            score_bonus += 1
        
        final_priority = base_priority + reliability_bonus + score_bonus
        return max(1, min(10, final_priority))
    
    async def _process_update_data(self, update: KnowledgeUpdate) -> Dict[str, Any]:
        """Processa dados da atualização"""
        processed_data = update.update_data.copy()
        
        # Adiciona metadados de processamento
        processed_data['processed_timestamp'] = datetime.now().isoformat()
        processed_data['update_id'] = update.id
        processed_data['priority'] = update.priority
        
        # Processa dados específicos do tipo de conteúdo
        if update.content_type == ContentType.METAR_TAF:
            processed_data = await self._process_metar_taf_data(processed_data)
        elif update.content_type == ContentType.NOTAM:
            processed_data = await self._process_notam_data(processed_data)
        elif update.content_type == ContentType.REGULATION:
            processed_data = await self._process_regulation_data(processed_data)
        elif update.content_type == ContentType.EMERGENCY:
            processed_data = await self._process_emergency_data(processed_data)
        
        return processed_data
    
    async def _process_metar_taf_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa dados de METAR/TAF"""
        # Implementação específica para METAR/TAF
        # Em produção, incluiria parsing detalhado e validação
        data['processed_type'] = 'metar_taf'
        return data
    
    async def _process_notam_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa dados de NOTAM"""
        # Implementação específica para NOTAM
        data['processed_type'] = 'notam'
        return data
    
    async def _process_regulation_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa dados de regulamentos"""
        # Implementação específica para regulamentos
        data['processed_type'] = 'regulation'
        return data
    
    async def _process_emergency_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa dados de emergência"""
        # Implementação específica para emergências
        data['processed_type'] = 'emergency'
        return data
    
    async def _update_pinecone_knowledge(self, update: KnowledgeUpdate, data: Dict[str, Any]):
        """Atualiza conhecimento no Pinecone"""
        # Implementação da integração com Pinecone
        # Em produção, incluiria upsert de vetores e metadados
        self.logger._log_info(f"Atualizando Pinecone para: {update.id}")
        
        # Simula atualização
        await asyncio.sleep(0.1)
    
    async def _update_embeddings(self, update: KnowledgeUpdate, data: Dict[str, Any]):
        """Atualiza embeddings"""
        # Implementação da atualização de embeddings
        # Em produção, incluiria geração de novos embeddings
        self.logger._log_info(f"Atualizando embeddings para: {update.id}")
        
        # Simula atualização
        await asyncio.sleep(0.1)
    
    def _generate_content_hash(self, result: SearchResult) -> str:
        """Gera hash do conteúdo"""
        content = f"{result.title}{result.snippet}{result.content or ''}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _generate_update_id(self, url: str, content_hash: str) -> str:
        """Gera ID único para atualização"""
        combined = f"{url}{content_hash}{datetime.now().isoformat()}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _is_already_processed(self, content_hash: str) -> bool:
        """Verifica se conteúdo já foi processado"""
        # Verifica cache
        if content_hash in self.update_cache:
            return True
        
        # Verifica histórico
        for update in self.update_history:
            if update.content_hash == content_hash:
                return True
        
        return False
    
    def _cache_update(self, update: KnowledgeUpdate):
        """Armazena atualização no cache"""
        self.update_cache[update.content_hash] = {
            'update': update,
            'timestamp': datetime.now()
        }
        
        # Limita tamanho do cache
        if len(self.update_cache) > 1000:
            # Remove entradas mais antigas
            oldest_key = min(
                self.update_cache.keys(),
                key=lambda k: self.update_cache[k]['timestamp']
            )
            del self.update_cache[oldest_key]
    
    def _update_metrics(self, successful_updates: int, total_updates: int):
        """Atualiza métricas do atualizador"""
        self.metrics.total_updates += total_updates
        self.metrics.successful_updates += successful_updates
        self.metrics.failed_updates += (total_updates - successful_updates)
        
        # Atualiza taxa de sucesso
        if self.metrics.total_updates > 0:
            self.metrics.success_rate = self.metrics.successful_updates / self.metrics.total_updates
        
        self.metrics.last_update = datetime.now()
    
    def get_metrics(self) -> UpdateMetrics:
        """Retorna métricas atuais do atualizador"""
        return self.metrics
    
    def get_pending_updates(self) -> List[KnowledgeUpdate]:
        """Retorna atualizações pendentes"""
        return self.pending_updates.copy()
    
    def get_update_history(self) -> List[KnowledgeUpdate]:
        """Retorna histórico de atualizações"""
        return self.update_history.copy()
    
    def clear_cache(self):
        """Limpa o cache de atualizações"""
        self.update_cache.clear()
        self.logger._log_info("Cache de atualizações limpo")
    
    def clear_history(self):
        """Limpa o histórico de atualizações"""
        self.update_history.clear()
        self.logger._log_info("Histórico de atualizações limpo") 