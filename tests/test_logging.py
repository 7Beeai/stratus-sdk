"""
Testes para o Sistema de Logging Estruturado do Stratus.IA
Testes de nível mundial para sistema crítico de aviação.
"""

import pytest
import json
import time
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

# Importar módulos do sistema de logging
import sys
sys.path.append('src')

from utils.logging import (
    StratusLogger,
    AviationContextExtractor,
    UrgencyClassifier,
    LogLevel,
    UrgencyLevel,
    get_logger,
    setup_logging,
    log_agent_action,
    log_safety_violation,
    log_api_call,
    log_performance_metric,
    log_regulatory_compliance,
    log_user_interaction
)


class TestAviationContextExtractor:
    """Testes para extração de contexto de aviação"""
    
    def test_extract_icao_codes_brazilian_airports(self):
        """Testa extração de códigos ICAO de aeroportos brasileiros"""
        text = "Voo de SBGR para SBSP com escala em SBRJ"
        codes = AviationContextExtractor.extract_icao_codes(text)
        assert "SBGR" in codes
        assert "SBSP" in codes
        assert "SBRJ" in codes
        assert len(codes) == 3
    
    def test_extract_icao_codes_international(self):
        """Testa extração de códigos ICAO internacionais"""
        text = "Rota internacional: KJFK, EGLL, LFPG"
        codes = AviationContextExtractor.extract_icao_codes(text)
        assert "KJFK" in codes
        assert "EGLL" in codes
        assert "LFPG" in codes
    
    def test_extract_aircraft_types(self):
        """Testa extração de tipos de aeronave"""
        text = "Operação com B737, A320 e E190"
        types = AviationContextExtractor.extract_aircraft_types(text)
        assert "B737" in types
        assert "A320" in types
        assert "E190" in types
    
    def test_extract_regulations(self):
        """Testa extração de regulamentações"""
        text = "Conforme RBAC 91 e IS 91-001"
        regulations = AviationContextExtractor.extract_regulations(text)
        assert "RBAC 91" in regulations
        assert "IS 91-001" in regulations
    
    def test_extract_frequencies(self):
        """Testa extração de frequências de rádio"""
        text = "Frequência 118.100 MHz para torre"
        frequencies = AviationContextExtractor.extract_frequencies(text)
        assert "118.100" in frequencies
    
    def test_extract_coordinates(self):
        """Testa extração de coordenadas geográficas"""
        text = "Posição: 23°32′07″S 046°38′34″W"
        coordinates = AviationContextExtractor.extract_coordinates(text)
        assert len(coordinates) > 0
        assert "23°32′07″S" in coordinates[0]


class TestUrgencyClassifier:
    """Testes para classificação de urgência"""
    
    def test_emergency_classification(self):
        """Testa classificação de emergência"""
        message = "Mayday mayday mayday, falha de motor"
        urgency = UrgencyClassifier.classify_urgency(message)
        assert urgency == UrgencyLevel.EMERGENCY
    
    def test_priority_classification(self):
        """Testa classificação de prioridade"""
        message = "METAR SBGR urgente para decolagem"
        urgency = UrgencyClassifier.classify_urgency(message)
        assert urgency == UrgencyLevel.PRIORITY
    
    def test_routine_classification(self):
        """Testa classificação de rotina"""
        message = "Consulta sobre regulamentação geral"
        urgency = UrgencyClassifier.classify_urgency(message)
        assert urgency == UrgencyLevel.ROUTINE
    
    def test_emergency_keywords(self):
        """Testa todas as palavras-chave de emergência"""
        emergency_messages = [
            "emergência a bordo",
            "emergency situation",
            "mayday call",
            "pan pan pan",
            "falha crítica",
            "motor failure",
            "pressurization loss",
            "smoke in cockpit",
            "fire on board",
            "ditching required"
        ]
        
        for message in emergency_messages:
            urgency = UrgencyClassifier.classify_urgency(message)
            assert urgency == UrgencyLevel.EMERGENCY, f"Falhou para: {message}"
    
    def test_priority_keywords(self):
        """Testa palavras-chave de prioridade"""
        priority_messages = [
            "decolagem imediata",
            "takeoff clearance",
            "pouso urgente",
            "weather briefing",
            "METAR request",
            "TAF information",
            "NOTAM alert"
        ]
        
        for message in priority_messages:
            urgency = UrgencyClassifier.classify_urgency(message)
            assert urgency == UrgencyLevel.PRIORITY, f"Falhou para: {message}"


class TestStratusLogger:
    """Testes para o logger principal"""
    
    @pytest.fixture
    def logger(self):
        """Fixture para logger de teste"""
        return StratusLogger(environment="test")
    
    def test_logger_initialization(self, logger):
        """Testa inicialização do logger"""
        assert logger.environment == "test"
        assert logger.trace_id is not None
        assert logger.start_time > 0
    
    def test_extract_aviation_context(self, logger):
        """Testa extração de contexto de aviação"""
        message = "Voo SBGR-SBSP com B737 conforme RBAC 91"
        context = logger.extract_aviation_context(message)
        
        assert "icao_codes" in context
        assert "aircraft_types" in context
        assert "regulations" in context
        assert "SBGR" in context["icao_codes"]
        assert "SBSP" in context["icao_codes"]
        assert "B737" in context["aircraft_types"]
        assert "RBAC 91" in context["regulations"]
    
    def test_determine_urgency(self, logger):
        """Testa determinação de urgência"""
        emergency_msg = "Mayday, falha de motor"
        priority_msg = "METAR urgente"
        routine_msg = "Consulta geral"
        
        assert logger.determine_urgency(emergency_msg) == UrgencyLevel.EMERGENCY
        assert logger.determine_urgency(priority_msg) == UrgencyLevel.PRIORITY
        assert logger.determine_urgency(routine_msg) == UrgencyLevel.ROUTINE
    
    def test_log_agent_action_success(self, logger):
        """Testa log de ação de agente com sucesso"""
        with patch.object(logger, '_log_info') as mock_log:
            logger.log_agent_action(
                agent_name="WeatherAgent",
                action="get_metar",
                message="METAR SBGR",
                user_id="pilot_123",
                duration_ms=150.5,
                success=True
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "WeatherAgent" in call_args[0][0]
            assert call_args[1]["agent_name"] == "WeatherAgent"
            assert call_args[1]["action"] == "get_metar"
            assert call_args[1]["success"] is True
    
    def test_log_agent_action_failure(self, logger):
        """Testa log de ação de agente com falha"""
        with patch.object(logger, '_log_error') as mock_log:
            logger.log_agent_action(
                agent_name="WeatherAgent",
                action="get_metar",
                message="METAR SBGR",
                user_id="pilot_123",
                success=False
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "Falha" in call_args[0][0]
            assert call_args[1]["success"] is False
    
    def test_log_safety_violation(self, logger):
        """Testa log de violação de segurança"""
        with patch.object(logger, '_log_critical') as mock_log:
            logger.log_safety_violation(
                violation_type="INVALID_ICAO",
                message="Código ICAO inválido: XYZ",
                agent_name="WeatherAgent",
                user_id="pilot_123",
                severity="HIGH"
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "VIOLAÇÃO DE SEGURANÇA" in call_args[0][0]
            assert call_args[1]["violation_type"] == "INVALID_ICAO"
            assert call_args[1]["severity"] == "HIGH"
    
    def test_log_api_call_success(self, logger):
        """Testa log de chamada de API com sucesso"""
        with patch.object(logger, '_log_info') as mock_log:
            logger.log_api_call(
                api_name="REDEMET",
                endpoint="/metar/SBGR",
                method="GET",
                status_code=200,
                duration_ms=45.2,
                user_id="pilot_123",
                cache_hit=False
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "REDEMET" in call_args[0][0]
            assert call_args[1]["status_code"] == 200
            assert call_args[1]["cache_hit"] is False
    
    def test_log_api_call_error(self, logger):
        """Testa log de chamada de API com erro"""
        with patch.object(logger, '_log_error') as mock_log:
            logger.log_api_call(
                api_name="REDEMET",
                endpoint="/metar/SBGR",
                method="GET",
                status_code=500,
                duration_ms=1500.0,
                user_id="pilot_123",
                error_message="Internal server error"
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "erro 500" in call_args[0][0]
            assert call_args[1]["status_code"] == 500
    
    def test_log_performance_metric(self, logger):
        """Testa log de métrica de performance"""
        with patch.object(logger, '_log_info') as mock_log:
            logger.log_performance_metric(
                metric_name="response_time",
                value=1.5,
                unit="seconds",
                agent_name="WeatherAgent",
                user_id="pilot_123"
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "response_time" in call_args[0][0]
            assert call_args[1]["value"] == 1.5
            assert call_args[1]["unit"] == "seconds"
    
    def test_log_performance_metric_threshold_exceeded(self, logger):
        """Testa log de métrica que excede threshold"""
        with patch.object(logger, '_log_warning') as mock_log:
            logger.log_performance_metric(
                metric_name="response_time",
                value=3.0,
                unit="seconds",
                threshold=2.0
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "excedeu threshold" in call_args[0][0]
            assert call_args[1]["threshold_exceeded"] is True
    
    def test_log_regulatory_compliance_violation(self, logger):
        """Testa log de violação regulatória"""
        with patch.object(logger, '_log_critical') as mock_log:
            logger.log_regulatory_compliance(
                regulation="RBAC 91",
                compliance_status="VIOLATION",
                message="Voo VFR sem plano de voo",
                agent_name="RegulatoryAgent",
                user_id="pilot_123"
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "VIOLAÇÃO REGULATÓRIA" in call_args[0][0]
            assert call_args[1]["compliance_status"] == "VIOLATION"
    
    def test_log_user_interaction(self, logger):
        """Testa log de interação do usuário"""
        with patch.object(logger, '_log_info') as mock_log:
            logger.log_user_interaction(
                interaction_type="weather_query",
                message="Qual o METAR do SBGR?",
                user_id="pilot_123",
                session_id="session_456",
                response_time_ms=1200.0
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "Interação do usuário" in call_args[0][0]
            assert call_args[1]["interaction_type"] == "weather_query"
            assert call_args[1]["session_id"] == "session_456"
    
    def test_new_trace(self, logger):
        """Testa criação de novo trace_id"""
        original_trace = logger.trace_id
        new_trace = logger.new_trace()
        
        assert new_trace != original_trace
        assert logger.trace_id == new_trace
    
    def test_get_performance_stats(self, logger):
        """Testa estatísticas de performance"""
        # Simular alguns logs
        logger.log_count = 10
        logger.total_log_time = 25.0
        logger.start_time = time.time() - 60  # 60 segundos atrás
        
        stats = logger.get_performance_stats()
        
        assert stats["total_logs"] == 10
        assert stats["average_log_time_ms"] == 2.5
        assert stats["total_log_time_ms"] == 25.0
        assert stats["uptime_seconds"] > 0


class TestLoggingFunctions:
    """Testes para funções convenientes de logging"""
    
    @patch('src.utils.logging.get_logger')
    def test_log_agent_action_function(self, mock_get_logger):
        """Testa função conveniente log_agent_action"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        log_agent_action(
            agent_name="WeatherAgent",
            action="get_metar",
            message="METAR SBGR",
            user_id="pilot_123"
        )
        
        mock_logger.log_agent_action.assert_called_once_with(
            "WeatherAgent", "get_metar", "METAR SBGR", "pilot_123"
        )
    
    @patch('src.utils.logging.get_logger')
    def test_log_safety_violation_function(self, mock_get_logger):
        """Testa função conveniente log_safety_violation"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        log_safety_violation(
            violation_type="INVALID_ICAO",
            message="Código inválido",
            agent_name="WeatherAgent",
            user_id="pilot_123"
        )
        
        mock_logger.log_safety_violation.assert_called_once_with(
            "INVALID_ICAO", "Código inválido", "WeatherAgent", "pilot_123"
        )
    
    @patch('src.utils.logging.get_logger')
    def test_log_api_call_function(self, mock_get_logger):
        """Testa função conveniente log_api_call"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        log_api_call(
            api_name="REDEMET",
            endpoint="/metar/SBGR",
            method="GET",
            status_code=200,
            duration_ms=45.2,
            user_id="pilot_123"
        )
        
        mock_logger.log_api_call.assert_called_once_with(
            "REDEMET", "/metar/SBGR", "GET", 200, 45.2, "pilot_123"
        )


class TestPerformanceTests:
    """Testes de performance do sistema de logging"""
    
    def test_logging_performance_under_load(self):
        """Testa performance do logging sob carga"""
        logger = StratusLogger(environment="test")
        
        start_time = time.time()
        
        # Simular 1000 logs rápidos
        for i in range(1000):
            logger.log_agent_action(
                agent_name="TestAgent",
                action="test_action",
                message=f"Test message {i}",
                user_id=f"user_{i}",
                duration_ms=1.0,
                success=True
            )
        
        end_time = time.time()
        total_time = (end_time - start_time) * 1000  # em ms
        
        # Verificar que 1000 logs foram processados em menos de 5 segundos
        assert total_time < 5000, f"Performance muito lenta: {total_time:.2f}ms"
        
        # Verificar estatísticas
        stats = logger.get_performance_stats()
        assert stats["total_logs"] == 1000
        assert stats["average_log_time_ms"] < 5.0  # < 5ms por log
    
    def test_trace_id_correlation(self):
        """Testa correlação de trace_ids"""
        logger1 = StratusLogger(environment="test")
        logger2 = StratusLogger(environment="test")
        
        # Verificar que trace_ids são únicos
        assert logger1.trace_id != logger2.trace_id
        
        # Verificar que novo trace mantém correlação
        original_trace = logger1.trace_id
        new_trace = logger1.new_trace()
        
        assert new_trace != original_trace
        assert logger1.trace_id == new_trace


class TestGoogleCloudIntegration:
    """Testes para integração com Google Cloud"""
    
    @patch('src.utils.logging.GOOGLE_CLOUD_AVAILABLE', True)
    @patch('src.utils.logging.cloud_logging')
    @patch('src.utils.logging.error_reporting')
    @patch.dict(os.environ, {'GOOGLE_CLOUD_PROJECT_ID': 'test-project'})
    def test_google_cloud_setup_success(self, mock_error_reporting, mock_cloud_logging):
        """Testa configuração bem-sucedida do Google Cloud"""
        mock_client = Mock()
        mock_cloud_logging.Client.return_value = mock_client
        
        logger = StratusLogger(environment="production")
        
        assert logger.cloud_client is not None
        assert logger.error_client is not None
        mock_client.setup_logging.assert_called_once()
    
    @patch('src.utils.logging.GOOGLE_CLOUD_AVAILABLE', False)
    def test_google_cloud_setup_failure(self):
        """Testa falha na configuração do Google Cloud"""
        logger = StratusLogger(environment="production")
        
        assert logger.cloud_client is None
        assert logger.error_client is None


if __name__ == "__main__":
    # Executar testes
    pytest.main([__file__, "-v"]) 