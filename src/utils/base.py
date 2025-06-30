"""
Stratus.IA - Utilitários Base
Sistema de IA para Aviação Civil Brasileira

Este módulo contém utilitários base utilizados por todo o sistema:
- Logging estruturado
- Tratamento de erros
- Funções auxiliares
- Decorators para performance
- Validações específicas para aviação
"""

import asyncio
import functools
import hashlib
import json
import logging
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from contextlib import asynccontextmanager, contextmanager

import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from config.settings import settings

# Type hints
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

# =============================================================================
# LOGGING ESTRUTURADO
# =============================================================================

def setup_structured_logging():
    """
    Configurar logging estruturado com contexto.
    
    Configura o sistema de logging para usar formato JSON estruturado
    com contexto automático para rastreamento de requests.
    """
    if settings.enable_structured_logging:
        # Configurar structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Configurar logging padrão
        logging.basicConfig(
            format="%(message)s",
            stream=structlog.dev.ConsoleRenderer(),
            level=getattr(logging, settings.log_level.value)
        )
    else:
        # Logging padrão
        logging.basicConfig(
            level=getattr(logging, settings.log_level.value),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Obter logger estruturado com contexto.
    
    Args:
        name: Nome do logger
        
    Returns:
        Logger estruturado
    """
    return structlog.get_logger(name)


# =============================================================================
# CONTEXTO DE REQUEST
# =============================================================================

class RequestContext:
    """Contexto de request para rastreamento."""
    
    def __init__(self, request_id: Optional[str] = None):
        self.request_id = request_id or str(uuid.uuid4())
        self.start_time = time.time()
        self.user_id: Optional[str] = None
        self.session_id: Optional[str] = None
        self.agent: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Converter contexto para dicionário."""
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "agent": self.agent,
            "processing_time": time.time() - self.start_time,
            **self.metadata
        }


# Contexto global por thread/task
_request_context: Optional[RequestContext] = None


def get_request_context() -> Optional[RequestContext]:
    """Obter contexto de request atual."""
    return _request_context


def set_request_context(context: RequestContext):
    """Definir contexto de request atual."""
    global _request_context
    _request_context = context


@contextmanager
def request_context(request_id: Optional[str] = None):
    """
    Context manager para contexto de request.
    
    Args:
        request_id: ID do request (opcional)
    """
    context = RequestContext(request_id)
    set_request_context(context)
    try:
        yield context
    finally:
        set_request_context(None)


# =============================================================================
# DECORATORS PARA PERFORMANCE
# =============================================================================

def timing_decorator(func: F) -> F:
    """
    Decorator para medir tempo de execução.
    
    Args:
        func: Função a ser decorada
        
    Returns:
        Função decorada
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Log de performance
            logger = get_logger(f"{func.__module__}.{func.__name__}")
            logger.info(
                "Função executada",
                function=func.__name__,
                execution_time=execution_time,
                success=True
            )
            
            # Verificar SLA crítico
            if execution_time > settings.max_response_time:
                logger.warning(
                    "SLA violado",
                    function=func.__name__,
                    execution_time=execution_time,
                    max_allowed=settings.max_response_time
                )
            
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger = get_logger(f"{func.__module__}.{func.__name__}")
            logger.error(
                "Erro na execução",
                function=func.__name__,
                execution_time=execution_time,
                error=str(e),
                success=False
            )
            raise
    
    return wrapper


def async_timing_decorator(func: F) -> F:
    """
    Decorator para medir tempo de execução de funções assíncronas.
    
    Args:
        func: Função assíncrona a ser decorada
        
    Returns:
        Função decorada
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Log de performance
            logger = get_logger(f"{func.__module__}.{func.__name__}")
            logger.info(
                "Função assíncrona executada",
                function=func.__name__,
                execution_time=execution_time,
                success=True
            )
            
            # Verificar SLA crítico
            if execution_time > settings.max_response_time:
                logger.warning(
                    "SLA violado",
                    function=func.__name__,
                    execution_time=execution_time,
                    max_allowed=settings.max_response_time
                )
            
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger = get_logger(f"{func.__module__}.{func.__name__}")
            logger.error(
                "Erro na execução assíncrona",
                function=func.__name__,
                execution_time=execution_time,
                error=str(e),
                success=False
            )
            raise
    
    return wrapper


def retry_with_backoff(
    max_attempts: Optional[int] = None,
    exceptions: tuple = (Exception,),
    base_delay: float = 1.0,
    max_delay: float = 60.0
):
    """
    Decorator para retry com backoff exponencial.
    
    Args:
        max_attempts: Número máximo de tentativas
        exceptions: Exceções que devem causar retry
        base_delay: Delay base em segundos
        max_delay: Delay máximo em segundos
        
    Returns:
        Decorator
    """
    if max_attempts is None:
        max_attempts = settings.max_retries
    
    def decorator(func: F) -> F:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=base_delay, max=max_delay),
            retry=retry_if_exception_type(exceptions),
            before_sleep=before_sleep_log(get_logger(func.__module__), logging.WARNING)
        )
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def async_retry_with_backoff(
    max_attempts: Optional[int] = None,
    exceptions: tuple = (Exception,),
    base_delay: float = 1.0,
    max_delay: float = 60.0
):
    """
    Decorator para retry com backoff exponencial para funções assíncronas.
    
    Args:
        max_attempts: Número máximo de tentativas
        exceptions: Exceções que devem causar retry
        base_delay: Delay base em segundos
        max_delay: Delay máximo em segundos
        
    Returns:
        Decorator
    """
    if max_attempts is None:
        max_attempts = settings.max_retries
    
    def decorator(func: F) -> F:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=base_delay, max=max_delay),
            retry=retry_if_exception_type(exceptions),
            before_sleep=before_sleep_log(get_logger(func.__module__), logging.WARNING)
        )
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# =============================================================================
# VALIDAÇÕES ESPECÍFICAS PARA AVIAÇÃO
# =============================================================================

def validate_icao_code(icao_code: str) -> bool:
    """
    Validar código ICAO.
    
    Args:
        icao_code: Código ICAO a ser validado
        
    Returns:
        True se válido, False caso contrário
    """
    if not icao_code:
        return False
    
    # Códigos ICAO têm 4 letras
    if len(icao_code) != 4:
        return False
    
    # Apenas letras maiúsculas
    if not icao_code.isalpha() or not icao_code.isupper():
        return False
    
    # Códigos brasileiros começam com SB
    if icao_code.startswith('SB'):
        return True
    
    # Outros códigos válidos (pode ser expandido)
    valid_prefixes = ['SB', 'SA', 'SC', 'SD', 'SE', 'SF', 'SG', 'SH', 'SI', 'SJ', 'SK', 'SL', 'SM', 'SN', 'SO', 'SP', 'SQ', 'SR', 'SS', 'ST', 'SU', 'SV', 'SW', 'SX', 'SY', 'SZ']
    return any(icao_code.startswith(prefix) for prefix in valid_prefixes)


def validate_metar_code(metar_code: str) -> bool:
    """
    Validar código METAR.
    
    Args:
        metar_code: Código METAR a ser validado
        
    Returns:
        True se válido, False caso contrário
    """
    if not metar_code:
        return False
    
    # METAR deve começar com "METAR"
    if not metar_code.startswith('METAR'):
        return False
    
    # Deve conter código ICAO
    parts = metar_code.split()
    if len(parts) < 2:
        return False
    
    icao_code = parts[1]
    return validate_icao_code(icao_code)


def validate_flight_number(flight_number: str) -> bool:
    """
    Validar número de voo.
    
    Args:
        flight_number: Número de voo a ser validado
        
    Returns:
        True se válido, False caso contrário
    """
    if not flight_number:
        return False
    
    # Número de voo deve ter pelo menos 3 caracteres
    if len(flight_number) < 3:
        return False
    
    # Deve começar com código de companhia (2-3 letras)
    # Seguido por números
    import re
    pattern = r'^[A-Z]{2,3}\d{1,4}$'
    return bool(re.match(pattern, flight_number))


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def generate_request_id() -> str:
    """
    Gerar ID único para request.
    
    Returns:
        ID único
    """
    return str(uuid.uuid4())


def hash_content(content: str) -> str:
    """
    Gerar hash SHA-256 do conteúdo.
    
    Args:
        content: Conteúdo a ser hasheado
        
    Returns:
        Hash SHA-256
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def format_timestamp(timestamp: Optional[datetime] = None) -> str:
    """
    Formatar timestamp em ISO 8601.
    
    Args:
        timestamp: Timestamp (usa UTC atual se None)
        
    Returns:
        Timestamp formatado
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    return timestamp.isoformat()


def safe_json_dumps(obj: Any) -> str:
    """
    Serializar objeto para JSON de forma segura.
    
    Args:
        obj: Objeto a ser serializado
        
    Returns:
        JSON string
    """
    try:
        return json.dumps(obj, default=str, ensure_ascii=False)
    except Exception:
        return str(obj)


def truncate_text(text: str, max_length: int = 1000) -> str:
    """
    Truncar texto para tamanho máximo.
    
    Args:
        text: Texto a ser truncado
        max_length: Tamanho máximo
        
    Returns:
        Texto truncado
    """
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


# =============================================================================
# CONTEXT MANAGERS
# =============================================================================

@contextmanager
def performance_monitor(operation_name: str):
    """
    Context manager para monitoramento de performance.
    
    Args:
        operation_name: Nome da operação
    """
    start_time = time.time()
    logger = get_logger("performance")
    
    try:
        yield
        execution_time = time.time() - start_time
        logger.info(
            "Operação concluída",
            operation=operation_name,
            execution_time=execution_time,
            success=True
        )
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(
            "Erro na operação",
            operation=operation_name,
            execution_time=execution_time,
            error=str(e),
            success=False
        )
        raise


@asynccontextmanager
async def async_performance_monitor(operation_name: str):
    """
    Context manager assíncrono para monitoramento de performance.
    
    Args:
        operation_name: Nome da operação
    """
    start_time = time.time()
    logger = get_logger("performance")
    
    try:
        yield
        execution_time = time.time() - start_time
        logger.info(
            "Operação assíncrona concluída",
            operation=operation_name,
            execution_time=execution_time,
            success=True
        )
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(
            "Erro na operação assíncrona",
            operation=operation_name,
            execution_time=execution_time,
            error=str(e),
            success=False
        )
        raise


# =============================================================================
# EXCEÇÕES CUSTOMIZADAS
# =============================================================================

class StratusIAError(Exception):
    """Exceção base do Stratus.IA."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class ValidationError(StratusIAError):
    """Erro de validação."""
    pass


class TimeoutError(StratusIAError):
    """Erro de timeout."""
    pass


class AviationSafetyError(StratusIAError):
    """Erro de segurança aeronáutica."""
    pass


class ConfigurationError(StratusIAError):
    """Erro de configuração."""
    pass


# =============================================================================
# CIRCUIT BREAKER ASSÍNCRONO
# =============================================================================

import asyncio
from enum import Enum as PyEnum
from typing import Callable, Awaitable

class CircuitBreakerState(PyEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """Circuit Breaker assíncrono para resiliência de sistemas críticos."""
    def __init__(self, failure_threshold: int = 3, timeout_duration: int = 10, half_open_max_calls: int = 1):
        self.failure_threshold = failure_threshold
        self.timeout_duration = timeout_duration
        self.half_open_max_calls = half_open_max_calls
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()

    def __call__(self, func: Callable[..., Awaitable]):
        async def wrapper(*args, **kwargs):
            async with self._lock:
                now = time.time()
                if self.state == CircuitBreakerState.OPEN:
                    if self.last_failure_time and (now - self.last_failure_time) > self.timeout_duration:
                        self.state = CircuitBreakerState.HALF_OPEN
                        self.half_open_calls = 0
                    else:
                        raise RuntimeError("Circuit breaker aberto - operação bloqueada.")
                if self.state == CircuitBreakerState.HALF_OPEN:
                    if self.half_open_calls >= self.half_open_max_calls:
                        raise RuntimeError("Circuit breaker half-open - limite de chamadas atingido.")
                    self.half_open_calls += 1
            try:
                result = await func(*args, **kwargs)
                async with self._lock:
                    self.failure_count = 0
                    if self.state == CircuitBreakerState.HALF_OPEN:
                        self.state = CircuitBreakerState.CLOSED
                return result
            except Exception as e:
                async with self._lock:
                    self.failure_count += 1
                    self.last_failure_time = time.time()
                    if self.failure_count >= self.failure_threshold:
                        self.state = CircuitBreakerState.OPEN
                raise
        return wrapper

# =============================================================================
# EXPONENTIAL BACKOFF
# =============================================================================

import random

class ExponentialBackoff:
    """Backoff exponencial com jitter para retry assíncrono."""
    def __init__(self, initial_delay: float = 0.5, max_delay: float = 4.0, multiplier: float = 2.0, jitter: bool = True):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        delay = min(self.initial_delay * (self.multiplier ** attempt), self.max_delay)
        if self.jitter:
            delay = delay * (0.5 + random.random() / 2)
        return delay

# =============================================================================
# CACHE MANAGER ASSÍNCRONO (IN-MEMORY)
# =============================================================================

class CacheEntry:
    def __init__(self, value: Any, expires_at: float):
        self.value = value
        self.expires_at = expires_at

class CacheManager:
    """Cache assíncrono in-memory com TTL por chave."""
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._cache.get(key)
            if entry and entry.expires_at > time.time():
                return entry.value
            elif entry:
                del self._cache[key]
            return None

    async def set(self, key: str, value: Any, ttl: int):
        async with self._lock:
            expires_at = time.time() + ttl
            self._cache[key] = CacheEntry(value, expires_at)

    async def clear(self):
        async with self._lock:
            self._cache.clear()

# =============================================================================
# INICIALIZAÇÃO
# =============================================================================

def initialize_utils():
    """
    Inicializar utilitários base.
    
    Configura logging estruturado e validações iniciais.
    """
    setup_structured_logging()
    
    logger = get_logger("utils.base")
    logger.info(
        "Utilitários base inicializados",
        environment=settings.environment.value,
        log_level=settings.log_level.value,
        max_response_time=settings.max_response_time
    )


# Inicializar automaticamente
if __name__ != "__main__":
    initialize_utils() 