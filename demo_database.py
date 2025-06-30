#!/usr/bin/env python3
"""
Demonstração do Sistema de Banco de Dados Stratus.IA
Usa SQLite para demonstração local sem necessidade de PostgreSQL
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
import uuid

# Adiciona src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.database.base import (
    UserProfile, UserRole, MemoryType, MessageType, 
    ConversationStatus, MemoryEntry, ConversationSession
)
from src.utils.logging import get_logger


class MockDatabaseSystem:
    """Sistema de banco de dados mock para demonstração"""
    
    def __init__(self):
        self.logger = get_logger()
        self.users = {}
        self.memories = {}
        self.conversations = {}
        self.messages = {}
        
        # Métricas
        self.metrics = {
            "total_users": 0,
            "total_memories": 0,
            "total_conversations": 0,
            "total_messages": 0
        }
    
    async def create_user(self, user_profile: UserProfile) -> bool:
        """Cria usuário mock"""
        try:
            self.users[user_profile.user_id] = user_profile
            self.metrics["total_users"] += 1
            
            self.logger._log_info(f"Created user: {user_profile.name} ({user_profile.role.value})")
            return True
            
        except Exception as e:
            self.logger._log_error(f"Failed to create user: {str(e)}")
            return False
    
    async def store_memory(
        self, 
        user_id: str, 
        key: str, 
        value: any,
        memory_type: MemoryType = MemoryType.MEDIUM_TERM,
        importance_score: float = 0.5,
        correlation_id: str = None
    ) -> str:
        """Armazena memória mock"""
        try:
            memory_id = f"mem_{len(self.memories) + 1}"
            
            memory_entry = MemoryEntry(
                memory_id=memory_id,
                user_id=user_id,
                correlation_id=correlation_id or str(uuid.uuid4()),
                memory_type=memory_type,
                key=key,
                value=value,
                importance_score=importance_score
            )
            
            self.memories[memory_id] = memory_entry
            self.metrics["total_memories"] += 1
            
            self.logger._log_info(f"Stored memory: {key} (type: {memory_type.value}, importance: {importance_score})")
            return memory_id
            
        except Exception as e:
            self.logger._log_error(f"Failed to store memory: {str(e)}")
            raise
    
    async def retrieve_memory(self, user_id: str, key: str = None) -> list[MemoryEntry]:
        """Recupera memórias mock"""
        try:
            if key:
                # Busca por chave específica
                memories = [
                    mem for mem in self.memories.values() 
                    if mem.user_id == user_id and mem.key == key
                ]
            else:
                # Busca todas as memórias do usuário
                memories = [
                    mem for mem in self.memories.values() 
                    if mem.user_id == user_id
                ]
            
            return memories
            
        except Exception as e:
            self.logger._log_error(f"Failed to retrieve memory: {str(e)}")
            return []
    
    async def retrieve_memory_by_correlation(self, user_id: str, correlation_id: str) -> list[MemoryEntry]:
        """Recupera memórias por correlation_id"""
        try:
            memories = [
                mem for mem in self.memories.values() 
                if mem.user_id == user_id and mem.correlation_id == correlation_id
            ]
            
            return memories
            
        except Exception as e:
            self.logger._log_error(f"Failed to retrieve memory by correlation: {str(e)}")
            return []
    
    async def create_conversation(
        self, 
        user_id: str, 
        title: str
    ) -> str:
        """Cria conversa mock"""
        try:
            conversation_id = f"conv_{len(self.conversations) + 1}"
            
            conversation = ConversationSession(
                conversation_id=conversation_id,
                user_id=user_id,
                title=title,
                status=ConversationStatus.ACTIVE
            )
            
            self.conversations[conversation_id] = conversation
            self.metrics["total_conversations"] += 1
            
            self.logger._log_info(f"Created conversation: {title}")
            return conversation_id
            
        except Exception as e:
            self.logger._log_error(f"Failed to create conversation: {str(e)}")
            raise
    
    async def add_message(
        self, 
        conversation_id: str,
        user_id: str,
        content: str,
        message_type: MessageType,
        agent_name: str = None
    ) -> str:
        """Adiciona mensagem mock"""
        try:
            message_id = f"msg_{len(self.messages) + 1}"
            
            # Atualiza conversa
            if conversation_id in self.conversations:
                conv = self.conversations[conversation_id]
                conv.message_count += 1
                conv.last_message_at = datetime.now()
            
            self.messages[message_id] = {
                "message_id": message_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "content": content,
                "message_type": message_type,
                "agent_name": agent_name,
                "timestamp": datetime.now()
            }
            
            self.metrics["total_messages"] += 1
            
            role = "Usuário" if message_type == MessageType.USER_INPUT else f"Agente ({agent_name})"
            self.logger._log_info(f"Added message: {role} - {content[:50]}...")
            
            return message_id
            
        except Exception as e:
            self.logger._log_error(f"Failed to add message: {str(e)}")
            raise
    
    async def get_user_stats(self, user_id: str) -> dict:
        """Obtém estatísticas do usuário"""
        try:
            user_memories = len([m for m in self.memories.values() if m.user_id == user_id])
            user_conversations = len([c for c in self.conversations.values() if c.user_id == user_id])
            user_messages = len([m for m in self.messages.values() if m["user_id"] == user_id])
            
            return {
                "user_id": user_id,
                "memories": user_memories,
                "conversations": user_conversations,
                "messages": user_messages
            }
            
        except Exception as e:
            self.logger._log_error(f"Failed to get user stats: {str(e)}")
            return {"error": str(e)}
    
    def get_system_stats(self) -> dict:
        """Obtém estatísticas do sistema"""
        return {
            "timestamp": datetime.now().isoformat(),
            "metrics": self.metrics,
            "cache_info": {
                "users_cache": len(self.users),
                "memories_cache": len(self.memories),
                "conversations_cache": len(self.conversations),
                "messages_cache": len(self.messages)
            }
        }


class DatabaseDemo:
    """Demonstração do sistema de banco de dados"""
    
    def __init__(self):
        self.logger = get_logger()
        self.db_system = MockDatabaseSystem()
    
    async def run_demo(self):
        """Executa demonstração completa"""
        self.logger._log_info("🚀 Iniciando Demonstração do Sistema de Banco de Dados Stratus.IA")
        self.logger._log_info("=" * 80)
        
        # 1. Criação de Usuários
        await self._demo_users()
        
        # 2. Gerenciamento de Memória
        await self._demo_memory()
        
        # 3. Histórico de Conversas
        await self._demo_conversations()
        
        # 4. Estatísticas e Métricas
        await self._demo_stats()
        
        self.logger._log_info("✅ Demonstração concluída com sucesso!")
    
    async def _demo_users(self):
        """Demonstra criação e gerenciamento de usuários"""
        self.logger._log_info("\n👥 DEMONSTRAÇÃO: Gerenciamento de Usuários")
        self.logger._log_info("-" * 50)
        
        # Cria usuários de exemplo
        users = [
            UserProfile(
                user_id="pilot_001",
                name="João Silva",
                email="joao.silva@aviacao.com",
                role=UserRole.PILOT,
                licenses=["PP", "PC", "IFR"],
                experience_level="advanced",
                preferences={"preferred_airport": "SBGR", "language": "pt-BR"}
            ),
            UserProfile(
                user_id="instructor_001", 
                name="Maria Santos",
                email="maria.santos@escola.com",
                role=UserRole.INSTRUCTOR,
                licenses=["PP", "PC", "FI"],
                experience_level="expert",
                preferences={"teaching_style": "hands_on", "language": "pt-BR"}
            ),
            UserProfile(
                user_id="mechanic_001",
                name="Carlos Oliveira", 
                email="carlos.oliveira@manutencao.com",
                role=UserRole.MECHANIC,
                licenses=["AMT"],
                experience_level="intermediate",
                preferences={"specialty": "engines", "language": "pt-BR"}
            )
        ]
        
        for user in users:
            success = await self.db_system.create_user(user)
            if success:
                self.logger._log_info(f"✅ Usuário criado: {user.name} ({user.role.value})")
            else:
                self.logger._log_error(f"❌ Falha ao criar usuário: {user.name}")
    
    async def _demo_memory(self):
        """Demonstra gerenciamento de memória"""
        self.logger._log_info("\n🧠 DEMONSTRAÇÃO: Gerenciamento de Memória")
        self.logger._log_info("-" * 50)
        
        # Cria correlation_id para testar correlação
        correlation_id = "flight_session_2024_001"
        
        # Armazena diferentes tipos de memória com correlation_id
        memories = [
            {
                "user_id": "pilot_001",
                "key": "preferred_aircraft",
                "value": "Cessna 172",
                "type": MemoryType.LONG_TERM,
                "importance": 0.8,
                "correlation_id": correlation_id
            },
            {
                "user_id": "pilot_001", 
                "key": "last_flight_route",
                "value": "SBGR -> SBSP",
                "type": MemoryType.SHORT_TERM,
                "importance": 0.6,
                "correlation_id": correlation_id
            },
            {
                "user_id": "pilot_001",
                "key": "emergency_procedures",
                "value": "Checklist de emergência memorizado",
                "type": MemoryType.CRITICAL,
                "importance": 0.95,
                "correlation_id": correlation_id
            },
            {
                "user_id": "instructor_001",
                "key": "student_progress",
                "value": {"student_id": "student_001", "hours": 45, "next_lesson": "IFR"},
                "type": MemoryType.MEDIUM_TERM,
                "importance": 0.7,
                "correlation_id": "training_session_2024_001"
            },
            {
                "user_id": "mechanic_001",
                "key": "maintenance_schedule",
                "value": "Próxima revisão: 15/01/2024",
                "type": MemoryType.MEDIUM_TERM,
                "importance": 0.8,
                "correlation_id": "maintenance_session_2024_001"
            }
        ]
        
        for mem in memories:
            memory_id = await self.db_system.store_memory(
                user_id=mem["user_id"],
                key=mem["key"],
                value=mem["value"],
                memory_type=mem["type"],
                importance_score=mem["importance"],
                correlation_id=mem["correlation_id"]
            )
            self.logger._log_info(f"✅ Memória armazenada: {mem['key']} (ID: {memory_id}, Correlation: {mem['correlation_id']})")
        
        # Recupera memórias por correlation_id
        correlated_memories = await self.db_system.retrieve_memory_by_correlation("pilot_001", correlation_id)
        self.logger._log_info(f"📋 Memórias correlacionadas do piloto: {len(correlated_memories)} encontradas")
        
        for memory in correlated_memories:
            self.logger._log_info(f"  - {memory.key}: {memory.value} (correlation_id: {memory.correlation_id})")
        
        # Recupera todas as memórias do piloto
        pilot_memories = await self.db_system.retrieve_memory("pilot_001")
        self.logger._log_info(f"📋 Total de memórias do piloto: {len(pilot_memories)} encontradas")
    
    async def _demo_conversations(self):
        """Demonstra histórico de conversas"""
        self.logger._log_info("\n💬 DEMONSTRAÇÃO: Histórico de Conversas")
        self.logger._log_info("-" * 50)
        
        # Cria conversa
        conv_id = await self.db_system.create_conversation(
            user_id="pilot_001",
            title="Consulta sobre condições meteorológicas"
        )
        
        # Adiciona mensagens (testando limite de 100)
        messages = [
            {
                "content": "Qual a condição meteorológica atual em SBGR?",
                "type": MessageType.USER_INPUT,
                "agent": None
            },
            {
                "content": "METAR SBGR 121200Z 08008KT 9999 SCT030 BKN100 25/18 Q1018",
                "type": MessageType.AGENT_RESPONSE,
                "agent": "Weather Agent"
            },
            {
                "content": "Há alguma restrição NOTAM para pouso?",
                "type": MessageType.USER_INPUT,
                "agent": None
            },
            {
                "content": "NOTAM A1234/23 - Pista 09L/27R fechada para manutenção até 15/01/2024",
                "type": MessageType.AGENT_RESPONSE,
                "agent": "NOTAM Agent"
            },
            {
                "content": "Obrigado pelas informações",
                "type": MessageType.USER_INPUT,
                "agent": None
            }
        ]
        
        for msg in messages:
            await self.db_system.add_message(
                conversation_id=conv_id,
                user_id="pilot_001",
                content=msg["content"],
                message_type=msg["type"],
                agent_name=msg["agent"]
            )
        
        self.logger._log_info(f"✅ Conversa criada com {len(messages)} mensagens")
        
        # Testa limite de mensagens (simula 100 mensagens)
        self.logger._log_info("\n🧪 Testando limite de 100 mensagens por conversa...")
        for i in range(95):  # Já temos 5, adiciona mais 95 para testar limite
            await self.db_system.add_message(
                conversation_id=conv_id,
                user_id="pilot_001",
                content=f"Mensagem de teste {i+6}",
                message_type=MessageType.USER_INPUT,
                agent_name=None
            )
        
        # A próxima mensagem deve criar nova conversa automaticamente
        new_conv_id = await self.db_system.add_message(
            conversation_id=conv_id,
            user_id="pilot_001",
            content="Esta mensagem deve criar nova conversa (limite atingido)",
            message_type=MessageType.USER_INPUT,
            agent_name=None
        )
        
        if new_conv_id != conv_id:
            self.logger._log_info(f"✅ Nova conversa criada automaticamente: {new_conv_id}")
        else:
            self.logger._log_info("⚠️ Limite de mensagens não foi aplicado")
    
    async def _demo_stats(self):
        """Demonstra estatísticas e métricas"""
        self.logger._log_info("\n📊 DEMONSTRAÇÃO: Estatísticas e Métricas")
        self.logger._log_info("-" * 50)
        
        # Estatísticas do sistema
        system_stats = self.db_system.get_system_stats()
        self.logger._log_info("📈 Estatísticas do Sistema:")
        self.logger._log_info(f"  - Total de usuários: {system_stats['metrics']['total_users']}")
        self.logger._log_info(f"  - Total de memórias: {system_stats['metrics']['total_memories']}")
        self.logger._log_info(f"  - Total de conversas: {system_stats['metrics']['total_conversations']}")
        self.logger._log_info(f"  - Total de mensagens: {system_stats['metrics']['total_messages']}")
        
        # Estatísticas por usuário
        for user_id in ["pilot_001", "instructor_001", "mechanic_001"]:
            user_stats = await self.db_system.get_user_stats(user_id)
            self.logger._log_info(f"\n👤 Estatísticas do usuário {user_id}:")
            self.logger._log_info(f"  - Memórias: {user_stats['memories']}")
            self.logger._log_info(f"  - Conversas: {user_stats['conversations']}")
            self.logger._log_info(f"  - Mensagens: {user_stats['messages']}")


async def main():
    """Função principal"""
    demo = DatabaseDemo()
    await demo.run_demo()


if __name__ == "__main__":
    asyncio.run(main()) 