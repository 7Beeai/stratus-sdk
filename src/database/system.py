"""
Sistema Integrado de Banco de Dados para Stratus.IA
Inclui integração PostgreSQL, gerenciador de memória, histórico de conversas e contexto do usuário
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional

from .integration import StratusPostgreSQLIntegration
from .memory import StratusMemoryManager
from .conversations import StratusConversationHistory
from .users import StratusUserContextStorage
from .base import MemoryType, MessageType, ConversationStatus
from src.utils.logging import get_logger


class StratusDatabaseSystem:
    """Sistema integrado de banco de dados para Stratus.IA"""
    
    def __init__(self, database_url: str):
        self.logger = get_logger()
        
        # Inicializa componentes
        self.db_integration = StratusPostgreSQLIntegration(database_url)
        self.memory_manager = StratusMemoryManager(self.db_integration)
        self.conversation_history = StratusConversationHistory(self.db_integration)
        self.user_context = StratusUserContextStorage(self.db_integration)
        
        # Métricas globais
        self.global_metrics = {
            "system_start_time": datetime.now(),
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "avg_response_time": 0.0
        }
        
        # Tarefas de manutenção
        self.maintenance_tasks = []
    
    async def initialize(self):
        """Inicializa sistema completo"""
        try:
            # Inicializa conexão com banco
            await self.db_integration.initialize()
            
            # Inicia tarefas de manutenção
            await self._start_maintenance_tasks()
            
            self.logger._log_info("Database system initialized successfully")
            
        except Exception as e:
            self.logger._log_error(f"Failed to initialize database system: {str(e)}")
            raise
    
    async def close(self):
        """Fecha sistema completo"""
        try:
            # Para tarefas de manutenção
            for task in self.maintenance_tasks:
                task.cancel()
            
            # Fecha conexões
            await self.db_integration.close()
            
            self.logger._log_info("Database system closed")
            
        except Exception as e:
            self.logger._log_error(f"Error closing database system: {str(e)}")
    
    async def _start_maintenance_tasks(self):
        """Inicia tarefas de manutenção automática"""
        
        # Limpeza de memória expirada (a cada hora)
        cleanup_task = asyncio.create_task(self._periodic_cleanup())
        self.maintenance_tasks.append(cleanup_task)
        
        # Arquivamento de conversas antigas (diário)
        archive_task = asyncio.create_task(self._periodic_archiving())
        self.maintenance_tasks.append(archive_task)
        
        # Backup automático (semanal)
        backup_task = asyncio.create_task(self._periodic_backup())
        self.maintenance_tasks.append(backup_task)
    
    async def _periodic_cleanup(self):
        """Limpeza periódica de dados expirados"""
        while True:
            try:
                await asyncio.sleep(3600)  # 1 hora
                
                # Limpa memórias expiradas
                deleted_count = await self.memory_manager.cleanup_expired_memory()
                
                if deleted_count > 0:
                    self.logger._log_info(f"Cleaned up {deleted_count} expired memory entries")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger._log_error(f"Error in periodic cleanup: {str(e)}")
    
    async def _periodic_archiving(self):
        """Arquivamento periódico de conversas antigas"""
        while True:
            try:
                await asyncio.sleep(86400)  # 24 horas
                
                # Arquiva conversas antigas
                archived_count = await self.conversation_history.archive_old_conversations()
                
                if archived_count > 0:
                    self.logger._log_info(f"Archived {archived_count} old conversations")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger._log_error(f"Error in periodic archiving: {str(e)}")
    
    async def _periodic_backup(self):
        """Backup periódico do banco de dados"""
        while True:
            try:
                await asyncio.sleep(604800)  # 7 dias
                
                # Cria backup
                backup_path = f"/tmp/stratus_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
                success = await self.db_integration.backup_database(backup_path)
                
                if success:
                    self.logger._log_info(f"Database backup created: {backup_path}")
                else:
                    self.logger._log_error("Failed to create database backup")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger._log_error(f"Error in periodic backup: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Verifica saúde do sistema completo"""
        
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "components": {}
        }
        
        try:
            # Verifica conexão com banco
            db_health = await self.db_integration.health_check()
            health_status["components"]["database"] = db_health
            
            # Verifica estatísticas de memória
            memory_stats = await self.memory_manager.get_memory_stats("system")
            health_status["components"]["memory"] = {
                "status": "healthy",
                "stats": memory_stats
            }
            
            # Verifica estatísticas de usuários
            user_stats = await self.user_context.get_user_stats()
            health_status["components"]["users"] = {
                "status": "healthy",
                "stats": user_stats
            }
            
            # Métricas globais
            health_status["global_metrics"] = self.global_metrics
            
            # Determina status geral
            if db_health["status"] != "healthy":
                health_status["overall_status"] = "unhealthy"
            
        except Exception as e:
            health_status["overall_status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status
    
    def get_function_tools(self) -> List:
        """Retorna function tools para uso em agentes"""
        
        # Para integração com agentes OpenAI, pode ser expandido conforme necessário
        return []

# Instância global do sistema de banco de dados

database_system = None

async def initialize_database_system(database_url: str):
    """Inicializa sistema global de banco de dados"""
    global database_system
    database_system = StratusDatabaseSystem(database_url)
    await database_system.initialize()
    return database_system 