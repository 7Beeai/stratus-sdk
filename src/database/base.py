"""
Estruturas Base do Sistema de Banco de Dados Stratus.IA
Enums, modelos Pydantic e estruturas de dados compartilhadas
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import json
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass


# Enums para classificação
class MessageType(Enum):
    USER_INPUT = "user_input"
    AGENT_RESPONSE = "agent_response"
    SYSTEM_MESSAGE = "system_message"
    ERROR_MESSAGE = "error_message"
    HANDOFF_MESSAGE = "handoff_message"


class ConversationStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    ARCHIVED = "archived"
    ERROR = "error"


class MemoryType(Enum):
    SHORT_TERM = "short_term"      # Sessão atual
    MEDIUM_TERM = "medium_term"    # Últimas 24h
    LONG_TERM = "long_term"        # Persistente
    CRITICAL = "critical"          # Informações críticas de segurança


class UserRole(Enum):
    PILOT = "pilot"
    INSTRUCTOR = "instructor"
    MECHANIC = "mechanic"
    CONTROLLER = "controller"
    DISPATCHER = "dispatcher"
    STUDENT = "student"
    ADMIN = "admin"


# Modelos Pydantic para dados
class UserProfile(BaseModel):
    """Perfil do usuário"""
    user_id: str = Field(description="ID único do usuário")
    name: str = Field(description="Nome do usuário")
    email: Optional[str] = Field(None, description="Email do usuário")
    role: UserRole = Field(description="Função do usuário na aviação")
    licenses: List[str] = Field(default_factory=list, description="Licenças e habilitações")
    experience_level: str = Field(description="Nível de experiência")
    preferred_language: str = Field(default="pt-BR", description="Idioma preferido")
    timezone: str = Field(default="America/Sao_Paulo", description="Fuso horário")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="Preferências do usuário")
    created_at: datetime = Field(default_factory=datetime.now, description="Data de criação")
    last_active: datetime = Field(default_factory=datetime.now, description="Última atividade")


class ConversationMessage(BaseModel):
    """Mensagem de conversa"""
    message_id: str = Field(description="ID único da mensagem")
    conversation_id: str = Field(description="ID da conversa")
    user_id: str = Field(description="ID do usuário")
    agent_name: Optional[str] = Field(None, description="Nome do agente que respondeu")
    message_type: MessageType = Field(description="Tipo da mensagem")
    content: str = Field(description="Conteúdo da mensagem")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadados da mensagem")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp da mensagem")
    tokens_used: Optional[int] = Field(None, description="Tokens utilizados")
    response_time: Optional[float] = Field(None, description="Tempo de resposta em segundos")


class ConversationSession(BaseModel):
    """Sessão de conversa"""
    conversation_id: str = Field(description="ID único da conversa")
    user_id: str = Field(description="ID do usuário")
    title: str = Field(description="Título da conversa")
    status: ConversationStatus = Field(description="Status da conversa")
    context: Dict[str, Any] = Field(default_factory=dict, description="Contexto da conversa")
    summary: Optional[str] = Field(None, description="Resumo da conversa")
    started_at: datetime = Field(default_factory=datetime.now, description="Início da conversa")
    last_message_at: datetime = Field(default_factory=datetime.now, description="Última mensagem")
    message_count: int = Field(default=0, description="Número de mensagens")
    total_tokens: int = Field(default=0, description="Total de tokens utilizados")


class MemoryEntry(BaseModel):
    """Entrada de memória"""
    memory_id: str = Field(description="ID único da memória")
    user_id: str = Field(description="ID do usuário")
    correlation_id: str = Field(description="ID único para correlacionar memórias do usuário")
    memory_type: MemoryType = Field(description="Tipo de memória")
    key: str = Field(description="Chave da memória")
    value: Any = Field(description="Valor armazenado")
    context: Dict[str, Any] = Field(default_factory=dict, description="Contexto adicional")
    importance_score: float = Field(ge=0.0, le=1.0, description="Score de importância")
    access_count: int = Field(default=0, description="Número de acessos")
    created_at: datetime = Field(default_factory=datetime.now, description="Data de criação")
    last_accessed: datetime = Field(default_factory=datetime.now, description="Último acesso")
    expires_at: Optional[datetime] = Field(None, description="Data de expiração")


@dataclass
class DatabaseMetrics:
    """Métricas do banco de dados"""
    total_users: int = 0
    active_conversations: int = 0
    total_messages: int = 0
    total_memory_entries: int = 0
    avg_response_time: float = 0.0
    cache_hit_rate: float = 0.0
    last_backup: Optional[datetime] = None 