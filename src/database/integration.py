"""
PostgreSQL Integration para Stratus.IA
Integração robusta com PostgreSQL usando SQLAlchemy e asyncpg
"""

import asyncio
import logging
import json
import hashlib
import os
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import asyncpg
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Index, Float
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.dialects.postgresql import JSONB

from .base import DatabaseMetrics


class StratusPostgreSQLIntegration:
    """Integração robusta com PostgreSQL"""
    
    def __init__(self, database_url: str):
        self.logger = get_logger()
        self.database_url = database_url
        
        # Configuração do SQLAlchemy
        self.engine = create_async_engine(
            database_url,
            echo=False,  # Set to True for SQL debugging
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={
                "server_settings": {
                    "application_name": "stratus_ia",
                    "jit": "off"
                }
            }
        )
        
        # Session factory
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Metadata e tabelas
        self.metadata = MetaData()
        self._define_tables()
        
        # Pool de conexões diretas para operações específicas
        self.connection_pool = None
        
        # Cache em memória
        self.cache = {}
        self.cache_ttl = timedelta(minutes=15)
        
        # Métricas
        self.metrics = DatabaseMetrics()
    
    def _define_tables(self):
        """Define estrutura das tabelas"""
        
        # Tabela de usuários
        self.users_table = Table(
            'users',
            self.metadata,
            Column('user_id', String(36), primary_key=True),
            Column('name', String(255), nullable=False),
            Column('email', String(255), unique=True),
            Column('role', String(50), nullable=False),
            Column('licenses', JSONB),
            Column('experience_level', String(50)),
            Column('preferred_language', String(10), default='pt-BR'),
            Column('timezone', String(50), default='America/Sao_Paulo'),
            Column('preferences', JSONB),
            Column('created_at', DateTime, default=datetime.now),
            Column('last_active', DateTime, default=datetime.now),
            Column('is_active', Boolean, default=True),
            Index('idx_users_email', 'email'),
            Index('idx_users_role', 'role'),
            Index('idx_users_last_active', 'last_active')
        )
        
        # Tabela de conversas
        self.conversations_table = Table(
            'conversations',
            self.metadata,
            Column('conversation_id', String(36), primary_key=True),
            Column('user_id', String(36), ForeignKey('users.user_id'), nullable=False),
            Column('title', String(500), nullable=False),
            Column('status', String(20), default='active'),
            Column('context', JSONB),
            Column('summary', Text),
            Column('started_at', DateTime, default=datetime.now),
            Column('last_message_at', DateTime, default=datetime.now),
            Column('message_count', Integer, default=0),
            Column('total_tokens', Integer, default=0),
            Index('idx_conversations_user_id', 'user_id'),
            Index('idx_conversations_status', 'status'),
            Index('idx_conversations_last_message', 'last_message_at')
        )
        
        # Tabela de mensagens
        self.messages_table = Table(
            'messages',
            self.metadata,
            Column('message_id', String(36), primary_key=True),
            Column('conversation_id', String(36), ForeignKey('conversations.conversation_id'), nullable=False),
            Column('user_id', String(36), ForeignKey('users.user_id'), nullable=False),
            Column('agent_name', String(100)),
            Column('message_type', String(20), nullable=False),
            Column('content', Text, nullable=False),
            Column('metadata', JSONB),
            Column('timestamp', DateTime, default=datetime.now),
            Column('tokens_used', Integer),
            Column('response_time', Float),
            Index('idx_messages_conversation_id', 'conversation_id'),
            Index('idx_messages_user_id', 'user_id'),
            Index('idx_messages_timestamp', 'timestamp'),
            Index('idx_messages_type', 'message_type')
        )
        
        # Tabela de memória
        self.memory_table = Table(
            'memory_entries',
            self.metadata,
            Column('memory_id', String(36), primary_key=True),
            Column('user_id', String(36), ForeignKey('users.user_id'), nullable=False),
            Column('memory_type', String(20), nullable=False),
            Column('key', String(255), nullable=False),
            Column('value', JSONB, nullable=False),
            Column('context', JSONB),
            Column('importance_score', Float, default=0.5),
            Column('access_count', Integer, default=0),
            Column('created_at', DateTime, default=datetime.now),
            Column('last_accessed', DateTime, default=datetime.now),
            Column('expires_at', DateTime),
            Index('idx_memory_user_id', 'user_id'),
            Index('idx_memory_type', 'memory_type'),
            Index('idx_memory_key', 'key'),
            Index('idx_memory_importance', 'importance_score'),
            Index('idx_memory_expires', 'expires_at')
        )
        
        # Tabela de auditoria
        self.audit_table = Table(
            'audit_log',
            self.metadata,
            Column('audit_id', String(36), primary_key=True),
            Column('user_id', String(36)),
            Column('action', String(100), nullable=False),
            Column('table_name', String(50)),
            Column('record_id', String(36)),
            Column('old_values', JSONB),
            Column('new_values', JSONB),
            Column('timestamp', DateTime, default=datetime.now),
            Column('ip_address', String(45)),
            Column('user_agent', String(500)),
            Index('idx_audit_user_id', 'user_id'),
            Index('idx_audit_action', 'action'),
            Index('idx_audit_timestamp', 'timestamp')
        )
    
    async def initialize(self):
        """Inicializa conexão e cria tabelas"""
        try:
            # Cria pool de conexões diretas
            self.connection_pool = await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            
            # Cria tabelas se não existirem
            async with self.engine.begin() as conn:
                await conn.run_sync(self.metadata.create_all)
            
            self.logger._log_info("PostgreSQL integration initialized successfully")
            
        except Exception as e:
            self.logger._log_error(f"Failed to initialize PostgreSQL: {str(e)}")
            raise
    
    async def close(self):
        """Fecha conexões"""
        try:
            if self.connection_pool:
                await self.connection_pool.close()
            
            await self.engine.dispose()
            
            self.logger._log_info("PostgreSQL connections closed")
            
        except Exception as e:
            self.logger._log_error(f"Error closing PostgreSQL connections: {str(e)}")
    
    @asynccontextmanager
    async def get_session(self):
        """Context manager para sessões"""
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Executa query SQL direta"""
        try:
            async with self.connection_pool.acquire() as conn:
                if params:
                    result = await conn.fetch(query, *params.values())
                else:
                    result = await conn.fetch(query)
                
                return [dict(row) for row in result]
                
        except Exception as e:
            self.logger._log_error(f"Query execution failed: {str(e)}")
            raise
    
    async def execute_transaction(self, operations: List[Tuple[str, Dict]]) -> bool:
        """Executa múltiplas operações em transação"""
        try:
            async with self.connection_pool.acquire() as conn:
                async with conn.transaction():
                    for query, params in operations:
                        if params:
                            await conn.execute(query, *params.values())
                        else:
                            await conn.execute(query)
                
                return True
                
        except Exception as e:
            self.logger._log_error(f"Transaction failed: {str(e)}")
            return False
    
    def _get_cache_key(self, table: str, key: str) -> str:
        """Gera chave de cache"""
        return f"{table}:{hashlib.md5(key.encode()).hexdigest()}"
    
    def _is_cache_valid(self, timestamp: datetime) -> bool:
        """Verifica se cache ainda é válido"""
        return datetime.now() - timestamp < self.cache_ttl
    
    async def get_cached_or_fetch(
        self, 
        cache_key: str, 
        fetch_func: callable,
        *args, **kwargs
    ) -> Any:
        """Obtém dados do cache ou executa função de busca"""
        
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if self._is_cache_valid(timestamp):
                self.metrics.cache_hit_rate = min(self.metrics.cache_hit_rate + 0.01, 1.0)
                return cached_data
        
        # Cache miss - busca dados
        data = await fetch_func(*args, **kwargs)
        self.cache[cache_key] = (data, datetime.now())
        
        # Limita tamanho do cache
        if len(self.cache) > 1000:
            # Remove entradas mais antigas
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        
        self.metrics.cache_hit_rate = max(self.metrics.cache_hit_rate - 0.01, 0.0)
        return data
    
    async def health_check(self) -> Dict[str, Any]:
        """Verifica saúde da conexão"""
        try:
            start_time = datetime.now()
            
            # Testa conexão básica
            async with self.connection_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            # Obtém estatísticas do pool
            pool_stats = {
                "size": self.connection_pool.get_size(),
                "max_size": self.connection_pool.get_max_size(),
                "min_size": self.connection_pool.get_min_size(),
                "idle_connections": self.connection_pool.get_idle_size()
            }
            
            return {
                "status": "healthy",
                "response_time": response_time,
                "pool_stats": pool_stats,
                "cache_size": len(self.cache),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def backup_database(self, backup_path: str) -> bool:
        """Cria backup do banco de dados"""
        try:
            # Extrai informações da URL
            parsed = urlparse(self.database_url)
            
            # Comando pg_dump
            cmd = [
                "pg_dump",
                f"--host={parsed.hostname}",
                f"--port={parsed.port or 5432}",
                f"--username={parsed.username}",
                f"--dbname={parsed.path[1:]}",  # Remove leading /
                "--format=custom",
                "--no-password",
                f"--file={backup_path}"
            ]
            
            # Define variável de ambiente para senha
            env = os.environ.copy()
            env["PGPASSWORD"] = parsed.password
            
            # Executa backup
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.metrics.last_backup = datetime.now()
                self.logger._log_info(f"Database backup created: {backup_path}")
                return True
            else:
                self.logger._log_error(f"Backup failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger._log_error(f"Backup error: {str(e)}")
            return False


# Import do logger do Stratus.IA
from src.utils.logging import get_logger 