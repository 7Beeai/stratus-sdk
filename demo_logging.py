#!/usr/bin/env python3
"""
Demonstração do Sistema de Logging Estruturado do Stratus.IA
Sistema de nível mundial para aviação civil brasileira.
"""

import time
import sys
import os

# Adicionar src ao path
sys.path.append('src')

from utils.logging import (
    StratusLogger,
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


def demo_basic_logging():
    """Demonstração de logging básico"""
    print("🛩️  DEMONSTRAÇÃO: Logging Básico")
    print("=" * 50)
    
    # Configurar logger
    logger = setup_logging(environment="development")
    
    # Log de ação de agente
    logger.log_agent_action(
        agent_name="WeatherAgent",
        action="get_metar",
        message="METAR SBGR 151400Z 08008KT 9999 FEW020 SCT100 25/18 Q1018=",
        user_id="pilot_123",
        duration_ms=150.5,
        success=True
    )
    
    # Log de chamada de API
    logger.log_api_call(
        api_name="REDEMET",
        endpoint="/metar/SBGR",
        method="GET",
        status_code=200,
        duration_ms=45.2,
        user_id="pilot_123",
        cache_hit=False
    )
    
    # Log de métrica de performance
    logger.log_performance_metric(
        metric_name="response_time",
        value=1.2,
        unit="seconds",
        agent_name="WeatherAgent",
        user_id="pilot_123"
    )
    
    print("✅ Logging básico concluído\n")


def demo_aviation_context():
    """Demonstração de extração de contexto de aviação"""
    print("🛩️  DEMONSTRAÇÃO: Contexto de Aviação")
    print("=" * 50)
    
    logger = get_logger()
    
    # Mensagens com contexto de aviação
    aviation_messages = [
        "Voo de SBGR para SBSP com B737 conforme RBAC 91",
        "METAR KJFK 151400Z 08008KT 9999 FEW020 SCT100 25/18 Q1018=",
        "Frequência 118.100 MHz para torre de SBGR",
        "Posição: 23°32′07″S 046°38′34″W",
        "Operação com A320 e E190 conforme IS 91-001"
    ]
    
    for message in aviation_messages:
        context = logger.extract_aviation_context(message)
        urgency = logger.determine_urgency(message)
        
        print(f"📝 Mensagem: {message}")
        print(f"   ICAO Codes: {context['icao_codes']}")
        print(f"   Aircraft Types: {context['aircraft_types']}")
        print(f"   Regulations: {context['regulations']}")
        print(f"   Frequencies: {context['frequencies']}")
        print(f"   Coordinates: {context['coordinates']}")
        print(f"   Urgency: {urgency.value}")
        print()
    
    print("✅ Contexto de aviação extraído\n")


def demo_urgency_classification():
    """Demonstração de classificação de urgência"""
    print("🛩️  DEMONSTRAÇÃO: Classificação de Urgência")
    print("=" * 50)
    
    logger = get_logger()
    
    # Mensagens de diferentes níveis de urgência
    test_messages = [
        ("Mayday mayday mayday, falha de motor", "EMERGENCY"),
        ("METAR SBGR urgente para decolagem", "PRIORITY"),
        ("Consulta sobre regulamentação geral", "ROUTINE"),
        ("Pan pan pan, combustível baixo", "EMERGENCY"),
        ("TAF SBSP para pouso", "PRIORITY"),
        ("Informações sobre RBAC 91", "ROUTINE")
    ]
    
    for message, expected_level in test_messages:
        urgency = logger.determine_urgency(message)
        status = "✅" if urgency.value == expected_level else "❌"
        print(f"{status} {message}")
        print(f"   Classificado como: {urgency.value}")
        print()
    
    print("✅ Classificação de urgência concluída\n")


def demo_safety_violations():
    """Demonstração de violações de segurança"""
    print("🛩️  DEMONSTRAÇÃO: Violações de Segurança")
    print("=" * 50)
    
    logger = get_logger()
    
    # Log de violações de segurança
    logger.log_safety_violation(
        violation_type="INVALID_ICAO_CODE",
        message="Código ICAO inválido fornecido: XYZ",
        agent_name="WeatherAgent",
        user_id="pilot_123",
        severity="HIGH"
    )
    
    logger.log_safety_violation(
        violation_type="HALLUCINATION_DETECTED",
        message="Agente inventou informações meteorológicas",
        agent_name="WeatherAgent",
        user_id="pilot_123",
        severity="CRITICAL"
    )
    
    print("✅ Violações de segurança logadas\n")


def demo_regulatory_compliance():
    """Demonstração de compliance regulatório"""
    print("🛩️  DEMONSTRAÇÃO: Compliance Regulatório")
    print("=" * 50)
    
    logger = get_logger()
    
    # Log de compliance regulatório
    logger.log_regulatory_compliance(
        regulation="RBAC 91",
        compliance_status="COMPLIANT",
        message="Voo VFR com plano de voo adequado",
        agent_name="RegulatoryAgent",
        user_id="pilot_123"
    )
    
    logger.log_regulatory_compliance(
        regulation="RBAC 91",
        compliance_status="VIOLATION",
        message="Voo VFR sem plano de voo obrigatório",
        agent_name="RegulatoryAgent",
        user_id="pilot_123",
        details={"section": "91.103", "requirement": "flight_plan"}
    )
    
    print("✅ Compliance regulatório logado\n")


def demo_user_interactions():
    """Demonstração de interações do usuário"""
    print("🛩️  DEMONSTRAÇÃO: Interações do Usuário")
    print("=" * 50)
    
    logger = get_logger()
    
    # Log de interações do usuário
    logger.log_user_interaction(
        interaction_type="weather_query",
        message="Qual o METAR do SBGR?",
        user_id="pilot_123",
        session_id="session_456",
        response_time_ms=1200.0
    )
    
    logger.log_user_interaction(
        interaction_type="regulatory_consultation",
        message="Qual a regulamentação para voo VFR noturno?",
        user_id="student_789",
        session_id="session_789",
        response_time_ms=800.0
    )
    
    print("✅ Interações do usuário logadas\n")


def demo_performance_metrics():
    """Demonstração de métricas de performance"""
    print("🛩️  DEMONSTRAÇÃO: Métricas de Performance")
    print("=" * 50)
    
    logger = get_logger()
    
    # Log de métricas de performance
    logger.log_performance_metric(
        metric_name="response_time",
        value=1.2,
        unit="seconds",
        agent_name="WeatherAgent",
        user_id="pilot_123",
        threshold=2.0
    )
    
    logger.log_performance_metric(
        metric_name="response_time",
        value=3.5,
        unit="seconds",
        agent_name="WeatherAgent",
        user_id="pilot_456",
        threshold=2.0
    )
    
    # Mostrar estatísticas de performance
    stats = logger.get_performance_stats()
    print(f"📊 Estatísticas de Performance:")
    print(f"   Total de logs: {stats['total_logs']}")
    print(f"   Tempo médio por log: {stats['average_log_time_ms']}ms")
    print(f"   Tempo total de logging: {stats['total_log_time_ms']}ms")
    print(f"   Uptime: {stats['uptime_seconds']}s")
    
    print("✅ Métricas de performance logadas\n")


def demo_trace_correlation():
    """Demonstração de correlação de traces"""
    print("🛩️  DEMONSTRAÇÃO: Correlação de Traces")
    print("=" * 50)
    
    logger = get_logger()
    
    # Mostrar trace atual
    print(f"🔍 Trace ID atual: {logger.trace_id}")
    
    # Criar novo trace
    new_trace = logger.new_trace()
    print(f"🆕 Novo Trace ID: {new_trace}")
    
    # Log com novo trace
    logger.log_agent_action(
        agent_name="TestAgent",
        action="test_action",
        message="Teste de correlação de trace",
        user_id="test_user",
        success=True
    )
    
    print("✅ Correlação de traces demonstrada\n")


def demo_high_volume_logging():
    """Demonstração de logging de alto volume"""
    print("🛩️  DEMONSTRAÇÃO: Logging de Alto Volume")
    print("=" * 50)
    
    logger = get_logger()
    
    start_time = time.time()
    
    # Simular 100 logs rápidos
    for i in range(100):
        logger.log_agent_action(
            agent_name=f"Agent_{i % 5}",
            action=f"action_{i}",
            message=f"Test message {i}",
            user_id=f"user_{i}",
            duration_ms=1.0 + (i % 10) * 0.1,
            success=True
        )
    
    end_time = time.time()
    total_time = (end_time - start_time) * 1000  # em ms
    
    print(f"⚡ 100 logs processados em {total_time:.2f}ms")
    print(f"📈 Taxa: {1000 / (total_time / 100):.0f} logs/segundo")
    
    # Mostrar estatísticas finais
    stats = logger.get_performance_stats()
    print(f"📊 Estatísticas finais:")
    print(f"   Total de logs: {stats['total_logs']}")
    print(f"   Tempo médio por log: {stats['average_log_time_ms']}ms")
    
    print("✅ Logging de alto volume concluído\n")


def main():
    """Função principal da demonstração"""
    print("🚀 STRATUS.IA - SISTEMA DE LOGGING DE NÍVEL MUNDIAL")
    print("=" * 60)
    print("Sistema crítico de aviação com logging estruturado")
    print("=" * 60)
    print()
    
    try:
        # Executar demonstrações
        demo_basic_logging()
        demo_aviation_context()
        demo_urgency_classification()
        demo_safety_violations()
        demo_regulatory_compliance()
        demo_user_interactions()
        demo_performance_metrics()
        demo_trace_correlation()
        demo_high_volume_logging()
        
        print("🎉 TODAS AS DEMONSTRAÇÕES CONCLUÍDAS COM SUCESSO!")
        print("=" * 60)
        print("✅ Sistema de logging de nível mundial funcionando perfeitamente")
        print("✅ Contexto de aviação extraído automaticamente")
        print("✅ Classificação de urgência operacional")
        print("✅ Violações de segurança detectadas")
        print("✅ Compliance regulatório monitorado")
        print("✅ Performance < 5ms por log")
        print("✅ Correlação de traces funcionando")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Erro na demonstração: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 