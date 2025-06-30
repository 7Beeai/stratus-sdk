from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime

# Enums para API
class UserRole(Enum):
    PILOT = "pilot"
    INSTRUCTOR = "instructor"
    MECHANIC = "mechanic"
    CONTROLLER = "controller"
    DISPATCHER = "dispatcher"
    STUDENT = "student"
    ADMIN = "admin"

class MessageType(Enum):
    QUESTION = "question"
    EMERGENCY = "emergency"
    ROUTINE = "routine"
    TRAINING = "training"

class ResponseStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    PROCESSING = "processing"

# Modelos Pydantic para API
class UserRegistration(BaseModel):
    """Modelo para registro de usuário"""
    name: str = Field(..., min_length=2, max_length=100, description="Nome completo")
    email: str = Field(..., description="Email válido")
    password: str = Field(..., min_length=8, description="Senha (mínimo 8 caracteres)")
    role: UserRole = Field(..., description="Função na aviação")
    licenses: List[str] = Field(default_factory=list, description="Licenças e habilitações")
    experience_level: str = Field(..., description="Nível de experiência")
    
    @validator('email')
    def validate_email(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Email inválido')
        return v.lower()
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Senha deve ter pelo menos 8 caracteres')
        if not any(c.isupper() for c in v):
            raise ValueError('Senha deve conter pelo menos uma letra maiúscula')
        if not any(c.islower() for c in v):
            raise ValueError('Senha deve conter pelo menos uma letra minúscula')
        if not any(c.isdigit() for c in v):
            raise ValueError('Senha deve conter pelo menos um número')
        return v

class UserLogin(BaseModel):
    """Modelo para login de usuário"""
    email: str = Field(..., description="Email do usuário")
    password: str = Field(..., description="Senha do usuário")

class ChatMessage(BaseModel):
    """Modelo para mensagem de chat"""
    message: str = Field(..., min_length=1, max_length=5000, description="Mensagem do usuário")
    message_type: MessageType = Field(default=MessageType.QUESTION, description="Tipo da mensagem")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Contexto adicional")
    conversation_id: Optional[str] = Field(None, description="ID da conversa (opcional)")

class ChatResponse(BaseModel):
    """Modelo para resposta do chat"""
    response: str = Field(..., description="Resposta do agente")
    status: ResponseStatus = Field(..., description="Status da resposta")
    agent_name: str = Field(..., description="Nome do agente que respondeu")
    conversation_id: str = Field(..., description="ID da conversa")
    message_id: str = Field(..., description="ID da mensagem")
    processing_time: float = Field(..., description="Tempo de processamento em segundos")
    tokens_used: Optional[int] = Field(None, description="Tokens utilizados")
    safety_score: float = Field(..., description="Score de segurança (0.0 a 1.0)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadados adicionais")

class HealthStatus(BaseModel):
    """Modelo para status de saúde"""
    status: str = Field(..., description="Status geral (healthy/unhealthy)")
    timestamp: datetime = Field(..., description="Timestamp da verificação")
    version: str = Field(..., description="Versão da aplicação")
    uptime: float = Field(..., description="Tempo de atividade em segundos")
    components: Dict[str, Any] = Field(..., description="Status dos componentes")
    metrics: Dict[str, Any] = Field(..., description="Métricas do sistema")

class APIError(BaseModel):
    """Modelo para erros da API"""
    error: str = Field(..., description="Tipo do erro")
    message: str = Field(..., description="Mensagem de erro")
    details: Optional[Dict[str, Any]] = Field(None, description="Detalhes adicionais")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp do erro")
    request_id: str = Field(..., description="ID da requisição") 