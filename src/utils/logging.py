"""
Stratus.IA - Sistema de Logging Estruturado de Nível Mundial
Sistema crítico de aviação com logging para auditoria, debugging e compliance regulatório.
"""

import logging
import json
import uuid
import re
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from enum import Enum
import os

# Google Cloud imports (opcional para desenvolvimento local)
try:
    from google.cloud import logging as cloud_logging
    from google.cloud import error_reporting
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    cloud_logging = None
    error_reporting = None


class LogLevel(Enum):
    """Níveis de log específicos para aviação"""
    SAFETY_CRITICAL = "SAFETY_CRITICAL"
    REGULATORY = "REGULATORY" 
    PERFORMANCE = "PERFORMANCE"
    AGENT_ACTION = "AGENT_ACTION"
    API_CALL = "API_CALL"
    USER_INTERACTION = "USER_INTERACTION"


class UrgencyLevel(Enum):
    """Níveis de urgência para aviação"""
    ROUTINE = "ROUTINE"
    PRIORITY = "PRIORITY"
    EMERGENCY = "EMERGENCY"


class AviationContextExtractor:
    """Extrator de contexto específico de aviação"""
    
    # Padrões regex para extração de dados aeronáuticos
    ICAO_PATTERNS = [
        r'\b(SB[A-Z]{2})\b',  # Aeroportos brasileiros
        r'\b([A-Z]{4})\b',    # Códigos ICAO internacionais
    ]
    
    AIRCRAFT_PATTERNS = [
        r'\b(B737|A320|E190|C172|PA28|BE20|EMB|ATR)\w*\b',
        r'\b(Boeing|Airbus|Embraer|Cessna|Piper|Beechcraft)\s+\w*\b',
    ]
    
    REGULATION_PATTERNS = [
        r'\b(RBAC[-\s]?\d+[-\s]?\d*)\b',  # RBACs brasileiros
        r'\b(IS[-\s]?\d+[-\s]?\d*)\b',    # Instruções Suplementares
        r'\b(ICAO\s+Annex\s+\d+)\b',      # Anexos ICAO
    ]
    
    FREQUENCY_PATTERNS = [
        r'\b(\d{3}\.\d{3})\s*MHz\b',
        r'\b(\d{3}\.\d{3})\b',
    ]
    
    COORDINATE_PATTERNS = [
        r'\b(\d{2}°\d{2}′\d{2}″[NS])\s*(\d{3}°\d{2}′\d{2}″[EW])\b',
        r'\b(\d{2}:\d{2}:\d{2}[NS])\s*(\d{3}:\d{2}:\d{2}[EW])\b',
    ]
    
    @classmethod
    def extract_icao_codes(cls, text: str) -> List[str]:
        """Extrai códigos ICAO do texto"""
        codes = []
        for pattern in cls.ICAO_PATTERNS:
            matches = re.findall(pattern, text.upper())
            codes.extend(matches)
        return list(set(codes))  # Remove duplicatas
    
    @classmethod
    def extract_aircraft_types(cls, text: str) -> List[str]:
        """Extrai tipos de aeronave do texto"""
        types = []
        for pattern in cls.AIRCRAFT_PATTERNS:
            matches = re.findall(pattern, text.upper())
            types.extend(matches)
        return list(set(types))
    
    @classmethod
    def extract_regulations(cls, text: str) -> List[str]:
        """Extrai referências regulatórias do texto"""
        regulations = []
        for pattern in cls.REGULATION_PATTERNS:
            matches = re.findall(pattern, text.upper())
            regulations.extend(matches)
        return list(set(regulations))
    
    @classmethod
    def extract_frequencies(cls, text: str) -> List[str]:
        """Extrai frequências de rádio do texto"""
        frequencies = []
        for pattern in cls.FREQUENCY_PATTERNS:
            matches = re.findall(pattern, text.upper())
            frequencies.extend(matches)
        return list(set(frequencies))
    
    @classmethod
    def extract_coordinates(cls, text: str) -> List[str]:
        """Extrai coordenadas geográficas do texto"""
        coordinates = []
        for pattern in cls.COORDINATE_PATTERNS:
            matches = re.findall(pattern, text.upper())
            coordinates.extend([f"{lat} {lon}" for lat, lon in matches])
        return list(set(coordinates))


class UrgencyClassifier:
    """Classificador de urgência para mensagens de aviação"""
    
    EMERGENCY_KEYWORDS = [
        "emergência", "emergency", "mayday", "pan pan", "urgente",
        "falha", "failure", "pane", "combustível baixo", "fuel low",
        "motor failure", "falha de motor", "pressurization", "pressurização",
        "smoke", "fumaça", "fire", "incêndio", "ditching", "amerissagem"
    ]
    
    PRIORITY_KEYWORDS = [
        "decolagem", "takeoff", "pouso", "landing", "imediato",
        "agora", "hoje", "weather", "metar", "taf", "notam",
        "turbulence", "turbulência", "icing", "gelo", "wind shear",
        "microburst", "microexplosão", "thunderstorm", "tempestade"
    ]
    
    @classmethod
    def classify_urgency(cls, message: str, agent_classification: str = None) -> UrgencyLevel:
        """Classifica o nível de urgência da mensagem"""
        message_lower = message.lower()
        
        # Verificar palavras-chave de emergência
        if any(keyword in message_lower for keyword in cls.EMERGENCY_KEYWORDS):
            return UrgencyLevel.EMERGENCY
        
        # Verificar palavras-chave de prioridade
        if any(keyword in message_lower for keyword in cls.PRIORITY_KEYWORDS):
            return UrgencyLevel.PRIORITY
        
        # Verificar classificação do agente
        if agent_classification:
            agent_lower = agent_classification.lower()
            if any(keyword in agent_lower for keyword in cls.EMERGENCY_KEYWORDS):
                return UrgencyLevel.EMERGENCY
            if any(keyword in agent_lower for keyword in cls.PRIORITY_KEYWORDS):
                return UrgencyLevel.PRIORITY
        
        return UrgencyLevel.ROUTINE


class StructuredJSONFormatter(logging.Formatter):
    """Formatador JSON estruturado para logs"""
    
    def format(self, record):
        """Formata o registro de log em JSON estruturado"""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "log_type": getattr(record, 'log_type', 'GENERAL'),
            "trace_id": getattr(record, 'trace_id', 'unknown'),
            "message": record.getMessage(),
            "module": record.name,
            "function": record.funcName,
            "line": record.lineno,
            "process_id": record.process,
            "thread_id": record.thread,
        }
        
        # Adicionar contexto adicional se disponível
        if hasattr(record, 'aviation_context'):
            log_entry['aviation_context'] = record.aviation_context
        
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        
        if hasattr(record, 'agent_name'):
            log_entry['agent_name'] = record.agent_name
        
        if hasattr(record, 'urgency_level'):
            log_entry['urgency_level'] = record.urgency_level
        
        return json.dumps(log_entry, ensure_ascii=False)


class StratusLogger:
    """Logger principal do Stratus.IA com funcionalidades avançadas"""
    
    def __init__(self, environment: str = "production"):
        self.environment = environment
        self.trace_id = str(uuid.uuid4())
        self.start_time = time.time()
        
        # Configurar Google Cloud Logging
        self._setup_google_cloud()
        
        # Configurar logger estruturado
        self._setup_structured_logging()
        
        # Métricas de performance
        self.log_count = 0
        self.total_log_time = 0.0
    
    def _setup_google_cloud(self):
        """Configura integração com Google Cloud"""
        self.cloud_client = None
        self.error_client = None
        
        if (self.environment == "production" and 
            GOOGLE_CLOUD_AVAILABLE and 
            os.getenv('GOOGLE_CLOUD_PROJECT_ID')):
            
            try:
                self.cloud_client = cloud_logging.Client()
                self.cloud_client.setup_logging()
                self.error_client = error_reporting.Client()
                self._log_info("Google Cloud Logging configurado com sucesso")
            except Exception as e:
                self._log_warning(f"Falha ao configurar Google Cloud: {e}")
    
    def _setup_structured_logging(self):
        """Configura logging estruturado"""
        self.logger = logging.getLogger("stratus_ia")
        self.logger.setLevel(logging.DEBUG)
        
        # Limpar handlers existentes
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Handler para console com formatação JSON
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(StructuredJSONFormatter())
        self.logger.addHandler(console_handler)
        
        # Handler para arquivo em produção
        if self.environment == "production":
            file_handler = logging.FileHandler(f"logs/stratus_ia_{datetime.now().strftime('%Y%m%d')}.log")
            file_handler.setFormatter(StructuredJSONFormatter())
            self.logger.addHandler(file_handler)
    
    def _log_with_performance_tracking(self, level: str, message: str, **kwargs):
        """Log com tracking de performance"""
        start_time = time.time()
        
        # Adicionar trace_id e contexto aos kwargs
        kwargs['trace_id'] = self.trace_id
        kwargs['log_type'] = kwargs.get('log_type', 'GENERAL')
        
        # Registrar log
        if level == 'INFO':
            self.logger.info(message, extra=kwargs)
        elif level == 'ERROR':
            self.logger.error(message, extra=kwargs)
        elif level == 'CRITICAL':
            self.logger.critical(message, extra=kwargs)
        elif level == 'WARNING':
            self.logger.warning(message, extra=kwargs)
        else:
            self.logger.debug(message, extra=kwargs)
        
        # Atualizar métricas
        duration = (time.time() - start_time) * 1000  # em ms
        self.log_count += 1
        self.total_log_time += duration
        
        # Alertar se performance estiver ruim
        if duration > 5.0:  # > 5ms
            self._log_warning(f"Log lento detectado: {duration:.2f}ms", 
                            log_type=LogLevel.PERFORMANCE.value)
    
    def _log_info(self, message: str, **kwargs):
        """Log de informação"""
        self._log_with_performance_tracking('INFO', message, **kwargs)
    
    def _log_warning(self, message: str, **kwargs):
        """Log de aviso"""
        self._log_with_performance_tracking('WARNING', message, **kwargs)
    
    def _log_error(self, message: str, **kwargs):
        """Log de erro"""
        self._log_with_performance_tracking('ERROR', message, **kwargs)
    
    def _log_critical(self, message: str, **kwargs):
        """Log crítico"""
        self._log_with_performance_tracking('CRITICAL', message, **kwargs)
    
    def extract_aviation_context(self, message: str) -> Dict[str, Any]:
        """Extrai contexto específico de aviação da mensagem"""
        return {
            "icao_codes": AviationContextExtractor.extract_icao_codes(message),
            "aircraft_types": AviationContextExtractor.extract_aircraft_types(message),
            "regulations": AviationContextExtractor.extract_regulations(message),
            "frequencies": AviationContextExtractor.extract_frequencies(message),
            "coordinates": AviationContextExtractor.extract_coordinates(message),
        }
    
    def determine_urgency(self, message: str, agent_classification: str = None) -> UrgencyLevel:
        """Determina nível de urgência baseado no conteúdo da mensagem"""
        return UrgencyClassifier.classify_urgency(message, agent_classification)
    
    def log_agent_action(self, 
                        agent_name: str,
                        action: str,
                        message: str,
                        user_id: str,
                        duration_ms: float = None,
                        success: bool = True,
                        additional_context: Dict[str, Any] = None):
        """Log de ações de agentes com contexto de aviação"""
        
        aviation_context = self.extract_aviation_context(message)
        urgency = self.determine_urgency(message)
        
        log_data = {
            "log_type": LogLevel.AGENT_ACTION.value,
            "agent_name": agent_name,
            "action": action,
            "user_id": user_id,
            "message_preview": message[:100] + "..." if len(message) > 100 else message,
            "urgency_level": urgency.value,
            "aviation_context": aviation_context,
            "duration_ms": duration_ms,
            "success": success,
        }
        
        if additional_context:
            log_data.update(additional_context)
        
        if success:
            self._log_info(f"Agente {agent_name} executou {action}", **log_data)
        else:
            self._log_error(f"Falha na ação {action} do agente {agent_name}", **log_data)
    
    def log_safety_violation(self,
                           violation_type: str,
                           message: str,
                           agent_name: str,
                           user_id: str,
                           severity: str = "HIGH"):
        """Log de violações de segurança - CRÍTICO para aviação"""
        
        log_data = {
            "log_type": LogLevel.SAFETY_CRITICAL.value,
            "violation_type": violation_type,
            "severity": severity,
            "agent_name": agent_name,
            "user_id": user_id,
            "requires_human_review": True,
            "aviation_context": self.extract_aviation_context(message),
        }
        
        self._log_critical(f"VIOLAÇÃO DE SEGURANÇA: {violation_type} - {message}", **log_data)
        
        # Enviar para Google Cloud Error Reporting se em produção
        if (self.environment == "production" and 
            self.error_client and 
            severity in ["HIGH", "CRITICAL"]):
            try:
                self.error_client.report_exception()
            except Exception as e:
                self._log_error(f"Falha ao reportar erro para Google Cloud: {e}")
    
    def log_api_call(self,
                    api_name: str,
                    endpoint: str,
                    method: str,
                    status_code: int,
                    duration_ms: float,
                    user_id: str,
                    cache_hit: bool = False,
                    error_message: str = None):
        """Log de chamadas para APIs e MCPs"""
        
        log_data = {
            "log_type": LogLevel.API_CALL.value,
            "api_name": api_name,
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "cache_hit": cache_hit,
        }
        
        if error_message:
            log_data["error_message"] = error_message
        
        if status_code >= 400:
            self._log_error(f"API {api_name} retornou erro {status_code}", **log_data)
        else:
            self._log_info(f"API {api_name} chamada com sucesso", **log_data)
    
    def log_performance_metric(self,
                             metric_name: str,
                             value: float,
                             unit: str,
                             agent_name: str = None,
                             user_id: str = None,
                             threshold: float = None):
        """Log de métricas de performance para monitoramento"""
        
        log_data = {
            "log_type": LogLevel.PERFORMANCE.value,
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "agent_name": agent_name,
            "user_id": user_id,
        }
        
        if threshold and value > threshold:
            log_data["threshold_exceeded"] = True
            self._log_warning(f"Métrica {metric_name} excedeu threshold", **log_data)
        else:
            self._log_info(f"Métrica {metric_name}: {value} {unit}", **log_data)
    
    def log_regulatory_compliance(self,
                                regulation: str,
                                compliance_status: str,
                                message: str,
                                agent_name: str,
                                user_id: str,
                                details: Dict[str, Any] = None):
        """Log de compliance regulatório"""
        
        log_data = {
            "log_type": LogLevel.REGULATORY.value,
            "regulation": regulation,
            "compliance_status": compliance_status,
            "agent_name": agent_name,
            "user_id": user_id,
            "aviation_context": self.extract_aviation_context(message),
        }
        
        if details:
            log_data["details"] = details
        
        if compliance_status == "VIOLATION":
            self._log_critical(f"VIOLAÇÃO REGULATÓRIA: {regulation} - {message}", **log_data)
        elif compliance_status == "WARNING":
            self._log_warning(f"AVISO REGULATÓRIO: {regulation} - {message}", **log_data)
        else:
            self._log_info(f"Compliance {regulation}: {compliance_status} - {message}", **log_data)
    
    def log_user_interaction(self,
                           interaction_type: str,
                           message: str,
                           user_id: str,
                           session_id: str = None,
                           response_time_ms: float = None):
        """Log de interações do usuário"""
        
        log_data = {
            "log_type": LogLevel.USER_INTERACTION.value,
            "interaction_type": interaction_type,
            "user_id": user_id,
            "session_id": session_id,
            "response_time_ms": response_time_ms,
            "aviation_context": self.extract_aviation_context(message),
            "urgency_level": self.determine_urgency(message).value,
        }
        
        self._log_info(f"Interação do usuário: {interaction_type}", **log_data)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de performance do logging"""
        avg_time = self.total_log_time / self.log_count if self.log_count > 0 else 0
        return {
            "total_logs": self.log_count,
            "average_log_time_ms": round(avg_time, 2),
            "total_log_time_ms": round(self.total_log_time, 2),
            "uptime_seconds": round(time.time() - self.start_time, 2),
        }
    
    def new_trace(self) -> str:
        """Inicia um novo trace_id para correlação"""
        self.trace_id = str(uuid.uuid4())
        self._log_info("Novo trace iniciado", trace_id=self.trace_id)
        return self.trace_id


# Instância global do logger
_stratus_logger = None


def get_logger() -> StratusLogger:
    """Retorna instância global do Stratus logger"""
    global _stratus_logger
    if _stratus_logger is None:
        environment = os.getenv('ENVIRONMENT', 'production')
        _stratus_logger = StratusLogger(environment)
    return _stratus_logger


def setup_logging(environment: str = "production") -> StratusLogger:
    """Configura logging para Stratus.IA"""
    global _stratus_logger
    _stratus_logger = StratusLogger(environment)
    return _stratus_logger


def log_agent_action(agent_name: str, action: str, message: str, user_id: str, **kwargs):
    """Função conveniente para log de ações de agentes"""
    get_logger().log_agent_action(agent_name, action, message, user_id, **kwargs)


def log_safety_violation(violation_type: str, message: str, agent_name: str, user_id: str, **kwargs):
    """Função conveniente para log de violações de segurança"""
    get_logger().log_safety_violation(violation_type, message, agent_name, user_id, **kwargs)


def log_api_call(api_name: str, endpoint: str, method: str, status_code: int, duration_ms: float, user_id: str, **kwargs):
    """Função conveniente para log de chamadas de API"""
    get_logger().log_api_call(api_name, endpoint, method, status_code, duration_ms, user_id, **kwargs)


def log_performance_metric(metric_name: str, value: float, unit: str, **kwargs):
    """Função conveniente para log de métricas de performance"""
    get_logger().log_performance_metric(metric_name, value, unit, **kwargs)


def log_regulatory_compliance(regulation: str, compliance_status: str, message: str, agent_name: str, user_id: str, **kwargs):
    """Função conveniente para log de compliance regulatório"""
    get_logger().log_regulatory_compliance(regulation, compliance_status, message, agent_name, user_id, **kwargs)


def log_user_interaction(interaction_type: str, message: str, user_id: str, **kwargs):
    """Função conveniente para log de interações do usuário"""
    get_logger().log_user_interaction(interaction_type, message, user_id, **kwargs) 