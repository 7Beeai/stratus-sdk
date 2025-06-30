from fastapi import FastAPI, HTTPException, Depends, Request, Response, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from enum import Enum
import asyncio
import structlog
import os
import uuid
import time
from datetime import datetime
from contextlib import asynccontextmanager
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from src.api.auth import StratusAuthenticationSystem
from src.api.health import StratusHealthChecks
from src.api.monitoring import StratusMonitoring
from src.api.models import (
    UserRegistration, UserLogin, ChatMessage, ChatResponse, 
    HealthStatus, APIError, UserRole, MessageType, ResponseStatus
)

# Métricas Prometheus
REQUEST_COUNT = Counter('stratus_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('stratus_request_duration_seconds', 'Request duration')
ACTIVE_USERS = Gauge('stratus_active_users', 'Active users')
AGENT_RESPONSES = Counter('stratus_agent_responses_total', 'Agent responses', ['agent_name', 'status'])
SAFETY_VIOLATIONS = Counter('stratus_safety_violations_total', 'Safety violations', ['violation_type'])

class StratusAPIApplication:
    """Aplicação principal do Stratus.IA"""
    def __init__(self):
        self.logger = structlog.get_logger("stratus.api")
        self.start_time = datetime.now()
        self.version = os.getenv("STRATUS_VERSION", "1.0.0")
        self.config = self._load_config()
        self.redis_client = None
        self.limiter = None
        self.auth_system = None
        self.orchestrator = None
        self.app = self._create_app()
        self._setup_middlewares()
        self._setup_instrumentation()
    
    def _load_config(self) -> Dict[str, Any]:
        return {
            "debug": os.getenv("DEBUG", "false").lower() == "true",
            "host": os.getenv("HOST", "0.0.0.0"),
            "port": int(os.getenv("PORT", "8000")),
            "workers": int(os.getenv("WORKERS", "4")),
            "database_url": os.getenv("DATABASE_URL"),
            "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379"),
            "jwt_secret": os.getenv("JWT_SECRET", "your-secret-key"),
            "jwt_algorithm": os.getenv("JWT_ALGORITHM", "HS256"),
            "jwt_expiration": int(os.getenv("JWT_EXPIRATION", "86400")),
            "cors_origins": os.getenv("CORS_ORIGINS", "*").split(","),
            "trusted_hosts": os.getenv("TRUSTED_HOSTS", "*").split(","),
            "rate_limit_default": os.getenv("RATE_LIMIT_DEFAULT", "100/minute"),
            "rate_limit_auth": os.getenv("RATE_LIMIT_AUTH", "10/minute"),
            "rate_limit_chat": os.getenv("RATE_LIMIT_CHAT", "30/minute"),
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "pinecone_api_key": os.getenv("PINECONE_API_KEY"),
            "google_cloud_project": os.getenv("GOOGLE_CLOUD_PROJECT"),
            "environment": os.getenv("ENVIRONMENT", "development")
        }
    
    def _create_app(self) -> FastAPI:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await self._startup()
            yield
            await self._shutdown()
        
        app = FastAPI(
            title="Stratus.IA API",
            description="API para assistente de aviação com IA",
            version=self.version,
            docs_url="/docs" if self.config["debug"] else None,
            redoc_url="/redoc" if self.config["debug"] else None,
            openapi_url="/openapi.json" if self.config["debug"] else None,
            lifespan=lifespan
        )
        return app
    
    def _setup_middlewares(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config["cors_origins"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["*"],
        )
        
        if self.config["trusted_hosts"] != ["*"]:
            self.app.add_middleware(
                TrustedHostMiddleware,
                allowed_hosts=self.config["trusted_hosts"]
            )
        
        @self.app.middleware("http")
        async def request_id_middleware(request: Request, call_next):
            request_id = str(uuid.uuid4())
            request.state.request_id = request_id
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        
        @self.app.middleware("http")
        async def logging_middleware(request: Request, call_next):
            start_time = time.time()
            self.logger.info(
                "Request started",
                method=request.method,
                url=str(request.url),
                request_id=request.state.request_id
            )
            response = await call_next(request)
            duration = time.time() - start_time
            self.logger.info(
                "Request completed",
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                duration=duration,
                request_id=request.state.request_id
            )
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()
            REQUEST_DURATION.observe(duration)
            return response
    
    def _setup_routes(self):
        """Configura rotas da API"""
        
        # Rota de saúde
        @self.app.get("/health", response_model=HealthStatus)
        async def health_check():
            return await self._get_health_status()
        
        # Rota de métricas
        @self.app.get("/metrics")
        async def metrics():
            return Response(generate_latest(), media_type="text/plain")
        
        # Rotas de autenticação
        @self.app.post("/auth/register", response_model=Dict[str, str])
        async def register(request: Request, user_data: UserRegistration):
            return await self.auth_system.register_user(user_data)
        
        @self.app.post("/auth/login", response_model=Dict[str, str])
        async def login(request: Request, credentials: UserLogin):
            return await self.auth_system.login_user(credentials)
        
        @self.app.post("/auth/refresh", response_model=Dict[str, str])
        async def refresh_token(request: Request, current_user: dict = Depends(self.auth_system.get_current_user)):
            return await self.auth_system.refresh_token(current_user["user_id"])
        
        @self.app.post("/auth/logout")
        async def logout(current_user: dict = Depends(self.auth_system.get_current_user)):
            return await self.auth_system.logout_user(current_user["user_id"])
        
        # Rota principal de chat
        @self.app.post("/chat", response_model=ChatResponse)
        async def chat(
            request: Request,
            message: ChatMessage,
            background_tasks: BackgroundTasks,
            current_user: dict = Depends(self.auth_system.get_current_user)
        ):
            return await self._process_chat_message(message, current_user, background_tasks)
        
        # Rota de teste simples (sem autenticação)
        @self.app.get("/test")
        async def test():
            return {"message": "Stratus.IA API funcionando!", "timestamp": datetime.now().isoformat()}
        
        # Rota de informações do sistema
        @self.app.get("/info")
        async def info():
            return {
                "name": "Stratus.IA API",
                "version": self.version,
                "environment": self.config["environment"],
                "uptime": (datetime.now() - self.start_time).total_seconds(),
                "status": "operational"
            }
    
    def _setup_instrumentation(self):
        """Configura instrumentação e observabilidade"""
        pass  # Implementação futura
    
    async def _startup(self):
        """Inicialização da aplicação"""
        try:
            self.logger.info("Starting Stratus.IA API", version=self.version)
            
            # Inicializa sistema de autenticação
            self.auth_system = StratusAuthenticationSystem(
                jwt_secret=self.config["jwt_secret"],
                jwt_algorithm=self.config["jwt_algorithm"],
                jwt_expiration=self.config["jwt_expiration"],
                redis_client=self.redis_client
            )
            
            # Cria usuário admin padrão se não existir
            await self._create_default_admin()
            
            # Agora sim, configura as rotas
            self._setup_routes()
            
            self.logger.info("Stratus.IA API started successfully")
            
        except Exception as e:
            self.logger.error("Failed to start application", error=str(e))
            raise
    
    async def _shutdown(self):
        """Finalização da aplicação"""
        try:
            self.logger.info("Shutting down Stratus.IA API")
            self.logger.info("Stratus.IA API shutdown complete")
        except Exception as e:
            self.logger.error("Error during shutdown", error=str(e))
    
    async def _create_default_admin(self):
        """Cria usuário admin padrão para testes"""
        try:
            admin_data = UserRegistration(
                name="Admin Stratus",
                email="admin@stratus.ia",
                password="Admin123!",
                role=UserRole.ADMIN,
                licenses=["ADMIN"],
                experience_level="Administrador"
            )
            await self.auth_system.register_user(admin_data)
            self.logger.info("Default admin user created")
        except Exception as e:
            # Usuário já existe ou erro
            pass
    
    async def _process_chat_message(
        self, 
        message: ChatMessage, 
        current_user: dict,
        background_tasks: BackgroundTasks
    ) -> ChatResponse:
        """Processa mensagem de chat (versão simples)"""
        
        start_time = time.time()
        user_id = current_user["user_id"]
        
        try:
            # Simula processamento (versão simples para testes)
            await asyncio.sleep(0.1)  # Simula processamento
            
            # Resposta mock
            response_text = f"Olá {current_user['name']}! Sua mensagem foi: '{message.message}'. Processada pelo agente de teste."
            
            processing_time = time.time() - start_time
            
            # Cria resposta
            chat_response = ChatResponse(
                response=response_text,
                status=ResponseStatus.SUCCESS,
                agent_name="TestAgent",
                conversation_id=message.conversation_id or str(uuid.uuid4()),
                message_id=str(uuid.uuid4()),
                processing_time=processing_time,
                tokens_used=100,  # Mock
                safety_score=0.95,
                metadata={
                    "user_role": current_user["role"],
                    "message_type": message.message_type.value,
                    "test_mode": True
                }
            )
            
            # Métricas
            AGENT_RESPONSES.labels(
                agent_name=chat_response.agent_name,
                status="success"
            ).inc()
            
            return chat_response
            
        except Exception as e:
            self.logger.error(
                "Error processing chat message",
                error=str(e),
                user_id=user_id
            )
            
            AGENT_RESPONSES.labels(
                agent_name="error",
                status="error"
            ).inc()
            
            raise HTTPException(
                status_code=500,
                detail="Erro interno ao processar mensagem"
            )
    
    async def _get_health_status(self) -> HealthStatus:
        """Obtém status de saúde do sistema"""
        
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        # Verifica componentes
        components = {
            "auth": {"status": "healthy" if self.auth_system else "unhealthy"},
            "api": {"status": "healthy"},
            "version": self.version
        }
        
        # Status geral
        overall_status = "healthy"
        for component in components.values():
            if component.get("status") != "healthy":
                overall_status = "unhealthy"
                break
        
        # Métricas
        metrics = {
            "uptime": uptime,
            "version": self.version,
            "environment": self.config["environment"]
        }
        
        return HealthStatus(
            status=overall_status,
            timestamp=datetime.now(),
            version=self.version,
            uptime=uptime,
            components=components,
            metrics=metrics
        )

stratus_app = StratusAPIApplication() 