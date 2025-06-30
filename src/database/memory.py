"""
Memory Manager para Stratus.IA
Gerenciador de memória inteligente com análise de importância e TTL
"""

import asyncio
import json
import uuid
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from .base import MemoryType, MemoryEntry
from .integration import StratusPostgreSQLIntegration
from src.utils.logging import get_logger


class StratusMemoryManager:
    """Gerenciador de memória inteligente"""
    
    def __init__(self, db_integration: StratusPostgreSQLIntegration):
        self.logger = get_logger()
        self.db = db_integration
        
        # Configurações de TTL por tipo de memória
        self.memory_ttl = {
            MemoryType.SHORT_TERM: timedelta(hours=2),
            MemoryType.MEDIUM_TERM: timedelta(days=1),
            MemoryType.LONG_TERM: timedelta(days=365),
            MemoryType.CRITICAL: None  # Nunca expira
        }
        
        # Limites de memória por usuário
        self.memory_limits = {
            MemoryType.SHORT_TERM: 100,
            MemoryType.MEDIUM_TERM: 500,
            MemoryType.LONG_TERM: 1000,
            MemoryType.CRITICAL: 50
        }
        
        # Cache de memória ativa
        self.active_memory = {}
        
        # Agente de análise de importância (mock para demo)
        self.importance_agent = None  # Será inicializado quando necessário
    
    async def store_memory(
        self, 
        user_id: str, 
        key: str, 
        value: Any,
        memory_type: Optional[MemoryType] = None,
        context: Optional[Dict[str, Any]] = None,
        importance_score: Optional[float] = None,
        correlation_id: Optional[str] = None
    ) -> str:
        """Armazena entrada de memória"""
        
        try:
            # Gera ID único
            memory_id = str(uuid.uuid4())
            
            # Gera correlation_id se não fornecido
            if correlation_id is None:
                correlation_id = str(uuid.uuid4())
            
            # Analisa importância se não fornecida
            if importance_score is None:
                importance_score = await self._analyze_importance(key, value, context)
            
            # Determina tipo de memória se não fornecido
            if memory_type is None:
                memory_type = self._determine_memory_type(importance_score, context)
            
            # Calcula data de expiração
            expires_at = None
            if self.memory_ttl[memory_type]:
                expires_at = datetime.now() + self.memory_ttl[memory_type]
            
            # Verifica limites de memória
            await self._enforce_memory_limits(user_id, memory_type)
            
            # Cria entrada de memória
            memory_entry = MemoryEntry(
                memory_id=memory_id,
                user_id=user_id,
                correlation_id=correlation_id,
                memory_type=memory_type,
                key=key,
                value=value,
                context=context or {},
                importance_score=importance_score,
                expires_at=expires_at
            )
            
            # Armazena no banco
            async with self.db.get_session() as session:
                insert_query = """
                INSERT INTO memory_entries 
                (memory_id, user_id, correlation_id, memory_type, key, value, context, 
                 importance_score, created_at, last_accessed, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """
                
                await session.execute(
                    insert_query,
                    memory_id, user_id, correlation_id, memory_type.value, key, 
                    json.dumps(value), json.dumps(memory_entry.context),
                    importance_score, memory_entry.created_at, 
                    memory_entry.last_accessed, expires_at
                )
            
            # Adiciona ao cache ativo
            cache_key = f"{user_id}:{key}"
            self.active_memory[cache_key] = memory_entry
            
            self.logger._log_info(
                f"Memory stored: {key} for user {user_id}",
                extra={
                    "memory_id": memory_id,
                    "correlation_id": correlation_id,
                    "memory_type": memory_type.value,
                    "importance": importance_score
                }
            )
            
            return memory_id
            
        except Exception as e:
            self.logger._log_error(f"Failed to store memory: {str(e)}")
            raise
    
    async def retrieve_memory(
        self, 
        user_id: str, 
        key: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """Recupera entradas de memória"""
        
        try:
            # Verifica cache primeiro
            if key:
                cache_key = f"{user_id}:{key}"
                if cache_key in self.active_memory:
                    memory_entry = self.active_memory[cache_key]
                    await self._update_access_count(memory_entry.memory_id)
                    return [memory_entry]
            
            # Constrói query
            conditions = ["user_id = $1"]
            params = [user_id]
            param_count = 1
            
            if key:
                param_count += 1
                conditions.append(f"key = ${param_count}")
                params.append(key)
            
            if memory_type:
                param_count += 1
                conditions.append(f"memory_type = ${param_count}")
                params.append(memory_type.value)
            
            # Adiciona filtro de expiração
            conditions.append("(expires_at IS NULL OR expires_at > NOW())")
            
            query = f"""
            SELECT * FROM memory_entries 
            WHERE {' AND '.join(conditions)}
            ORDER BY importance_score DESC, last_accessed DESC
            LIMIT {limit}
            """
            
            results = await self.db.execute_query(query, dict(zip([f"${i+1}" for i in range(len(params))], params)))
            
            # Converte para objetos MemoryEntry
            memory_entries = []
            for row in results:
                memory_entry = MemoryEntry(
                    memory_id=row['memory_id'],
                    user_id=row['user_id'],
                    correlation_id=row['correlation_id'],
                    memory_type=MemoryType(row['memory_type']),
                    key=row['key'],
                    value=json.loads(row['value']),
                    context=json.loads(row['context']) if row['context'] else {},
                    importance_score=row['importance_score'],
                    access_count=row['access_count'],
                    created_at=row['created_at'],
                    last_accessed=row['last_accessed'],
                    expires_at=row['expires_at']
                )
                memory_entries.append(memory_entry)
                
                # Atualiza cache
                cache_key = f"{user_id}:{row['key']}"
                self.active_memory[cache_key] = memory_entry
            
            # Atualiza contadores de acesso
            for entry in memory_entries:
                await self._update_access_count(entry.memory_id)
            
            return memory_entries
            
        except Exception as e:
            self.logger._log_error(f"Failed to retrieve memory: {str(e)}")
            return []
    
    async def search_memory(
        self, 
        user_id: str, 
        search_term: str,
        memory_types: Optional[List[MemoryType]] = None,
        limit: int = 20
    ) -> List[MemoryEntry]:
        """Busca na memória por termo"""
        
        try:
            # Constrói condições de busca
            conditions = ["user_id = $1"]
            params = [user_id]
            param_count = 1
            
            # Busca textual em key e value
            param_count += 1
            conditions.append(f"(key ILIKE ${param_count} OR value::text ILIKE ${param_count})")
            params.append(f"%{search_term}%")
            
            # Filtro por tipos de memória
            if memory_types:
                type_values = [mt.value for mt in memory_types]
                param_count += 1
                conditions.append(f"memory_type = ANY(${param_count})")
                params.append(type_values)
            
            # Filtro de expiração
            conditions.append("(expires_at IS NULL OR expires_at > NOW())")
            
            query = f"""
            SELECT * FROM memory_entries 
            WHERE {' AND '.join(conditions)}
            ORDER BY importance_score DESC, 
                     CASE WHEN key ILIKE ${param_count-1} THEN 1 ELSE 2 END,
                     last_accessed DESC
            LIMIT {limit}
            """
            
            results = await self.db.execute_query(query, dict(zip([f"${i+1}" for i in range(len(params))], params)))
            
            # Converte resultados
            memory_entries = []
            for row in results:
                memory_entry = MemoryEntry(
                    memory_id=row['memory_id'],
                    user_id=row['user_id'],
                    correlation_id=row['correlation_id'],
                    memory_type=MemoryType(row['memory_type']),
                    key=row['key'],
                    value=json.loads(row['value']),
                    context=json.loads(row['context']) if row['context'] else {},
                    importance_score=row['importance_score'],
                    access_count=row['access_count'],
                    created_at=row['created_at'],
                    last_accessed=row['last_accessed'],
                    expires_at=row['expires_at']
                )
                memory_entries.append(memory_entry)
            
            return memory_entries
            
        except Exception as e:
            self.logger._log_error(f"Failed to search memory: {str(e)}")
            return []
    
    async def update_memory(
        self, 
        memory_id: str, 
        value: Optional[Any] = None,
        importance_score: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Atualiza entrada de memória"""
        
        try:
            updates = []
            params = []
            param_count = 0
            
            if value is not None:
                param_count += 1
                updates.append(f"value = ${param_count}")
                params.append(json.dumps(value))
            
            if importance_score is not None:
                param_count += 1
                updates.append(f"importance_score = ${param_count}")
                params.append(importance_score)
            
            if context is not None:
                param_count += 1
                updates.append(f"context = ${param_count}")
                params.append(json.dumps(context))
            
            if not updates:
                return True
            
            # Adiciona timestamp de atualização
            param_count += 1
            updates.append(f"last_accessed = ${param_count}")
            params.append(datetime.now())
            
            # ID da memória
            param_count += 1
            params.append(memory_id)
            
            query = f"""
            UPDATE memory_entries 
            SET {', '.join(updates)}
            WHERE memory_id = ${param_count}
            """
            
            await self.db.execute_query(query, dict(zip([f"${i+1}" for i in range(len(params))], params)))
            
            # Remove do cache para forçar reload
            for cache_key in list(self.active_memory.keys()):
                if self.active_memory[cache_key].memory_id == memory_id:
                    del self.active_memory[cache_key]
                    break
            
            return True
            
        except Exception as e:
            self.logger._log_error(f"Failed to update memory: {str(e)}")
            return False
    
    async def delete_memory(self, memory_id: str) -> bool:
        """Remove entrada de memória"""
        
        try:
            query = "DELETE FROM memory_entries WHERE memory_id = $1"
            await self.db.execute_query(query, {"$1": memory_id})
            
            # Remove do cache
            for cache_key in list(self.active_memory.keys()):
                if self.active_memory[cache_key].memory_id == memory_id:
                    del self.active_memory[cache_key]
                    break
            
            return True
            
        except Exception as e:
            self.logger._log_error(f"Failed to delete memory: {str(e)}")
            return False
    
    async def cleanup_expired_memory(self) -> int:
        """Remove memórias expiradas"""
        
        try:
            query = """
            DELETE FROM memory_entries 
            WHERE expires_at IS NOT NULL AND expires_at <= NOW()
            """
            
            result = await self.db.execute_query(query)
            deleted_count = len(result) if result else 0
            
            # Limpa cache
            expired_keys = []
            for cache_key, memory_entry in self.active_memory.items():
                if (memory_entry.expires_at and 
                    memory_entry.expires_at <= datetime.now()):
                    expired_keys.append(cache_key)
            
            for key in expired_keys:
                del self.active_memory[key]
            
            if deleted_count > 0:
                self.logger._log_info(f"Cleaned up {deleted_count} expired memory entries")
            
            return deleted_count
            
        except Exception as e:
            self.logger._log_error(f"Failed to cleanup expired memory: {str(e)}")
            return 0
    
    async def _analyze_importance(
        self, 
        key: str, 
        value: Any, 
        context: Optional[Dict[str, Any]]
    ) -> float:
        """Analisa importância da informação"""
        
        try:
            # Análise simples baseada em palavras-chave
            text_content = f"{key} {str(value)}".lower()
            
            # Palavras-chave de alta importância para aviação
            high_importance_keywords = [
                'emergency', 'emergência', 'critical', 'crítico', 'safety', 'segurança',
                'accident', 'acidente', 'incident', 'incidente', 'failure', 'falha',
                'weather', 'tempo', 'metar', 'taf', 'notam', 'restriction', 'restrição',
                'license', 'licença', 'certificate', 'certificado', 'medical', 'médico'
            ]
            
            # Palavras-chave de média importância
            medium_importance_keywords = [
                'preference', 'preferência', 'setting', 'configuração', 'airport', 'aeroporto',
                'aircraft', 'aeronave', 'route', 'rota', 'flight', 'voo', 'planning', 'planejamento'
            ]
            
            # Verifica contexto para indicadores específicos
            if context:
                if context.get('safety_critical'):
                    return 0.95
                if context.get('session_only'):
                    return 0.3
            
            # Conta palavras-chave
            high_count = sum(1 for keyword in high_importance_keywords if keyword in text_content)
            medium_count = sum(1 for keyword in medium_importance_keywords if keyword in text_content)
            
            # Calcula score baseado nas palavras-chave
            if high_count > 0:
                return min(0.9 + (high_count * 0.02), 1.0)
            elif medium_count > 0:
                return min(0.6 + (medium_count * 0.05), 0.8)
            else:
                return 0.5  # Score padrão
                
        except Exception as e:
            self.logger._log_warning(f"Failed to analyze importance: {str(e)}")
            return 0.5  # Score padrão em caso de erro
    
    def _determine_memory_type(
        self, 
        importance_score: float, 
        context: Optional[Dict[str, Any]]
    ) -> MemoryType:
        """Determina tipo de memória baseado na importância"""
        
        # Verifica contexto para indicadores específicos
        if context:
            if context.get('safety_critical'):
                return MemoryType.CRITICAL
            if context.get('session_only'):
                return MemoryType.SHORT_TERM
        
        # Baseado no score de importância
        if importance_score >= 0.9:
            return MemoryType.CRITICAL
        elif importance_score >= 0.7:
            return MemoryType.LONG_TERM
        elif importance_score >= 0.4:
            return MemoryType.MEDIUM_TERM
        else:
            return MemoryType.SHORT_TERM
    
    async def _enforce_memory_limits(self, user_id: str, memory_type: MemoryType):
        """Aplica limites de memória por usuário"""
        
        try:
            # Conta entradas atuais
            count_query = """
            SELECT COUNT(*) as count FROM memory_entries 
            WHERE user_id = $1 AND memory_type = $2 
            AND (expires_at IS NULL OR expires_at > NOW())
            """
            
            result = await self.db.execute_query(
                count_query, 
                {"$1": user_id, "$2": memory_type.value}
            )
            
            current_count = result[0]['count'] if result else 0
            limit = self.memory_limits[memory_type]
            
            # Remove entradas mais antigas se necessário
            if current_count >= limit:
                delete_count = current_count - limit + 1
                
                delete_query = """
                DELETE FROM memory_entries 
                WHERE memory_id IN (
                    SELECT memory_id FROM memory_entries 
                    WHERE user_id = $1 AND memory_type = $2
                    AND (expires_at IS NULL OR expires_at > NOW())
                    ORDER BY importance_score ASC, last_accessed ASC
                    LIMIT $3
                )
                """
                
                await self.db.execute_query(
                    delete_query,
                    {"$1": user_id, "$2": memory_type.value, "$3": delete_count}
                )
                
                self.logger._log_info(
                    f"Removed {delete_count} old {memory_type.value} memories for user {user_id}"
                )
                
        except Exception as e:
            self.logger._log_error(f"Failed to enforce memory limits: {str(e)}")
    
    async def _update_access_count(self, memory_id: str):
        """Atualiza contador de acesso"""
        
        try:
            query = """
            UPDATE memory_entries 
            SET access_count = access_count + 1, last_accessed = NOW()
            WHERE memory_id = $1
            """
            
            await self.db.execute_query(query, {"$1": memory_id})
            
        except Exception as e:
            self.logger._log_warning(f"Failed to update access count: {str(e)}")
    
    async def get_memory_stats(self, user_id: str) -> Dict[str, Any]:
        """Obtém estatísticas de memória do usuário"""
        
        try:
            stats_query = """
            SELECT 
                memory_type,
                COUNT(*) as count,
                AVG(importance_score) as avg_importance,
                MAX(last_accessed) as last_access
            FROM memory_entries 
            WHERE user_id = $1 
            AND (expires_at IS NULL OR expires_at > NOW())
            GROUP BY memory_type
            """
            
            results = await self.db.execute_query(stats_query, {"$1": user_id})
            
            stats = {
                "user_id": user_id,
                "total_entries": 0,
                "by_type": {},
                "cache_entries": len([k for k in self.active_memory.keys() if k.startswith(f"{user_id}:")])
            }
            
            for row in results:
                memory_type = row['memory_type']
                stats["by_type"][memory_type] = {
                    "count": row['count'],
                    "avg_importance": float(row['avg_importance']),
                    "last_access": row['last_access']
                }
                stats["total_entries"] += row['count']
            
            return stats
            
        except Exception as e:
            self.logger._log_error(f"Failed to get memory stats: {str(e)}")
            return {"user_id": user_id, "error": str(e)}
    
    async def get_memories_by_correlation_id(
        self, 
        user_id: str, 
        correlation_id: str,
        limit: int = 50
    ) -> List[MemoryEntry]:
        """Recupera todas as memórias relacionadas por correlation_id"""
        
        try:
            query = """
            SELECT * FROM memory_entries 
            WHERE user_id = $1 AND correlation_id = $2
            AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY importance_score DESC, created_at DESC
            LIMIT $3
            """
            
            results = await self.db.execute_query(
                query, 
                {"$1": user_id, "$2": correlation_id, "$3": limit}
            )
            
            # Converte para objetos MemoryEntry
            memory_entries = []
            for row in results:
                memory_entry = MemoryEntry(
                    memory_id=row['memory_id'],
                    user_id=row['user_id'],
                    correlation_id=row['correlation_id'],
                    memory_type=MemoryType(row['memory_type']),
                    key=row['key'],
                    value=json.loads(row['value']),
                    context=json.loads(row['context']) if row['context'] else {},
                    importance_score=row['importance_score'],
                    access_count=row['access_count'],
                    created_at=row['created_at'],
                    last_accessed=row['last_accessed'],
                    expires_at=row['expires_at']
                )
                memory_entries.append(memory_entry)
                
                # Atualiza cache
                cache_key = f"{user_id}:{row['key']}"
                self.active_memory[cache_key] = memory_entry
            
            # Atualiza contadores de acesso
            for entry in memory_entries:
                await self._update_access_count(entry.memory_id)
            
            self.logger._log_info(
                f"Retrieved {len(memory_entries)} memories by correlation_id {correlation_id}",
                extra={"user_id": user_id, "correlation_id": correlation_id}
            )
            
            return memory_entries
            
        except Exception as e:
            self.logger._log_error(f"Failed to get memories by correlation_id: {str(e)}")
            return [] 