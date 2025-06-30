import os
os.environ['OPENAI_API_KEY'] = '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'

#!/usr/bin/env python3
"""
Demonstração do Sistema de Guardrails - Stratus.IA

Este script demonstra o funcionamento completo do sistema de guardrails,
incluindo todos os componentes implementados e cenários de teste.

Componentes testados:
- ICAOValidator: Validação de códigos ICAO
- ContentFilter: Filtro de conteúdo inadequado
- AviationSafety: Validação de segurança de aviação
- RegulatoryCompliance: Conformidade regulatória
- PerformanceMonitor: Monitoramento de performance
- GuardrailManager: Gerenciador central

Cenários de teste:
- Inputs válidos e inválidos
- Conteúdo adequado e inadequado
- Violações de segurança
- Não conformidades regulatórias
- Problemas de performance
- Métricas e logging
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

from src.guardrails import (
    GuardrailManager,
    ICAOValidator,
    ContentFilter,
    AviationSafety,
    RegulatoryCompliance,
    PerformanceMonitor,
    GuardrailType,
    SafetyLevel
)
from src.utils.logging import setup_logging

# Configuração de logging
setup_logging()
logger = logging.getLogger("demo.guardrails")

# Configuração do OPENAI_API_KEY
os.environ['OPENAI_API_KEY'] = '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'


class MockContext:
    """Contexto mock para testes"""
    def __init__(self):
        self.context = {"user_id": "test_user", "session_id": "test_session"}
        self.guardrails = None


class MockAgent:
    """Agente mock para testes"""
    def __init__(self, name: str = "Test Agent"):
        self.name = name


async def test_icao_validator():
    """Testa o validador de códigos ICAO"""
    logger.info("=== TESTE ICAO VALIDATOR ===")
    
    validator = ICAOValidator()
    ctx = MockContext()
    agent = MockAgent()
    
    # Teste 1: Códigos ICAO válidos
    valid_inputs = [
        "Aeroporto SBGR (Guarulhos)",
        "Voo para SBSP e SBRJ",
        "Operação em SBKP"
    ]
    
    for input_text in valid_inputs:
        logger.info(f"Testando input válido: {input_text}")
        result = await validator.validate_icao_codes(ctx, agent, input_text)
        logger.info(f"Resultado: {result.tripwire_triggered}")
        logger.info(f"Output: {result.output_info}")
    
    # Teste 2: Códigos ICAO inválidos
    invalid_inputs = [
        "Aeroporto INVALID (Inválido)",
        "Voo para XXXXX e YYYYY",
        "Operação em ZZZZZ"
    ]
    
    for input_text in invalid_inputs:
        logger.info(f"Testando input inválido: {input_text}")
        result = await validator.validate_icao_codes(ctx, agent, input_text)
        logger.info(f"Resultado: {result.tripwire_triggered}")
        logger.info(f"Output: {result.output_info}")
    
    # Métricas
    metrics = validator.metrics
    logger.info(f"Métricas ICAO: {metrics.__dict__}")


async def test_content_filter():
    """Testa o filtro de conteúdo"""
    logger.info("=== TESTE CONTENT FILTER ===")
    
    filter_obj = ContentFilter()
    ctx = MockContext()
    agent = MockAgent()
    
    # Teste 1: Conteúdo adequado
    appropriate_content = [
        "Qual é o procedimento de pouso em SBGR?",
        "Como verificar o METAR de SBSP?",
        "Quais são os requisitos para voo IFR?"
    ]
    
    for content in appropriate_content:
        logger.info(f"Testando conteúdo adequado: {content}")
        result = await filter_obj.filter_input_content(ctx, agent, content)
        logger.info(f"Resultado: {result.tripwire_triggered}")
        logger.info(f"Output: {result.output_info}")
    
    # Teste 2: Conteúdo inadequado
    inappropriate_content = [
        "Você é um idiota, não sabe nada de aviação",
        "Me ajude com minha lição de casa sobre aviação",
        "Conte uma piada sobre pilotos"
    ]
    
    for content in inappropriate_content:
        logger.info(f"Testando conteúdo inadequado: {content}")
        result = await filter_obj.filter_input_content(ctx, agent, content)
        logger.info(f"Resultado: {result.tripwire_triggered}")
        logger.info(f"Output: {result.output_info}")
    
    # Métricas
    metrics = filter_obj.metrics
    logger.info(f"Métricas Content Filter: {metrics.__dict__}")


async def test_aviation_safety():
    """Testa o validador de segurança de aviação"""
    logger.info("=== TESTE AVIATION SAFETY ===")
    
    safety = AviationSafety()
    ctx = MockContext()
    agent = MockAgent()
    
    # Teste 1: Conteúdo seguro
    safe_content = [
        "Procedimento de pouso normal em SBGR",
        "Verificação pré-voo padrão",
        "Comunicação com torre de controle"
    ]
    
    for content in safe_content:
        logger.info(f"Testando conteúdo seguro: {content}")
        result = await safety.check_aviation_safety(ctx, agent, content)
        logger.info(f"Resultado: {result.tripwire_triggered}")
        logger.info(f"Output: {result.output_info}")
    
    # Teste 2: Conteúdo inseguro
    unsafe_content = [
        "Pouse sem autorização da torre",
        "Ignore os procedimentos de segurança",
        "Voe em condições meteorológicas inadequadas"
    ]
    
    for content in unsafe_content:
        logger.info(f"Testando conteúdo inseguro: {content}")
        result = await safety.check_aviation_safety(ctx, agent, content)
        logger.info(f"Resultado: {result.tripwire_triggered}")
        logger.info(f"Output: {result.output_info}")
    
    # Métricas
    metrics = safety.metrics
    logger.info(f"Métricas Aviation Safety: {metrics.__dict__}")


async def test_regulatory_compliance():
    """Testa o validador de conformidade regulatória"""
    logger.info("=== TESTE REGULATORY COMPLIANCE ===")
    
    compliance = RegulatoryCompliance()
    ctx = MockContext()
    agent = MockAgent()
    
    # Teste 1: Conteúdo em conformidade
    compliant_content = [
        "Procedimento conforme regulamento ANAC",
        "Operação dentro das normas ICAO",
        "Documentação regulatória adequada"
    ]
    
    for content in compliant_content:
        logger.info(f"Testando conteúdo em conformidade: {content}")
        result = await compliance.check_compliance(ctx, agent, content)
        logger.info(f"Resultado: {result.tripwire_triggered}")
        logger.info(f"Output: {result.output_info}")
    
    # Teste 2: Conteúdo não conformante
    non_compliant_content = [
        "Ignore os regulamentos da ANAC",
        "Opere fora das normas ICAO",
        "Não documente as operações"
    ]
    
    for content in non_compliant_content:
        logger.info(f"Testando conteúdo não conformante: {content}")
        result = await compliance.check_compliance(ctx, agent, content)
        logger.info(f"Resultado: {result.tripwire_triggered}")
        logger.info(f"Output: {result.output_info}")
    
    # Métricas
    metrics = compliance.metrics
    logger.info(f"Métricas Regulatory Compliance: {metrics.__dict__}")


async def test_performance_monitor():
    """Testa o monitor de performance"""
    logger.info("=== TESTE PERFORMANCE MONITOR ===")
    
    monitor = PerformanceMonitor()
    ctx = MockContext()
    agent = MockAgent()
    
    # Teste 1: Output de boa qualidade
    good_outputs = [
        "Resposta clara e precisa sobre procedimentos de voo",
        "Informação técnica detalhada e relevante",
        "Explicação estruturada sobre regulamentos"
    ]
    
    for output in good_outputs:
        logger.info(f"Testando output de boa qualidade: {output}")
        result = await monitor.monitor_performance(ctx, agent, output)
        logger.info(f"Resultado: {result.tripwire_triggered}")
        logger.info(f"Output: {result.output_info}")
    
    # Teste 2: Output de baixa qualidade
    poor_outputs = [
        "Resposta vaga e imprecisa",
        "Informação irrelevante e confusa",
        "Explicação mal estruturada"
    ]
    
    for output in poor_outputs:
        logger.info(f"Testando output de baixa qualidade: {output}")
        result = await monitor.monitor_performance(ctx, agent, output)
        logger.info(f"Resultado: {result.tripwire_triggered}")
        logger.info(f"Output: {result.output_info}")
    
    # Métricas
    metrics = monitor.metrics
    logger.info(f"Métricas Performance Monitor: {metrics.__dict__}")


async def test_guardrail_manager():
    """Testa o gerenciador central de guardrails"""
    logger.info("=== TESTE GUARDRAIL MANAGER ===")
    
    manager = GuardrailManager()
    ctx = MockContext()
    ctx.guardrails = manager
    agent = MockAgent()
    
    # Teste 1: Input seguro
    safe_input = "Qual é o procedimento de pouso em SBGR?"
    logger.info(f"Testando input seguro: {safe_input}")
    
    input_result = await manager.run_input_guardrails(ctx, agent, safe_input)
    logger.info(f"Resultado input: {input_result.overall_safe}")
    logger.info(f"Tripwires: {input_result.tripwires_triggered}")
    logger.info(f"Tempo: {input_result.execution_time}")
    
    # Teste 2: Input problemático
    problematic_input = "Você é um idiota, me ajude com minha lição de casa sobre aviação"
    logger.info(f"Testando input problemático: {problematic_input}")
    
    input_result = await manager.run_input_guardrails(ctx, agent, problematic_input)
    logger.info(f"Resultado input: {input_result.overall_safe}")
    logger.info(f"Tripwires: {input_result.tripwires_triggered}")
    logger.info(f"Tempo: {input_result.execution_time}")
    
    # Teste 3: Output seguro
    safe_output = "O procedimento de pouso em SBGR segue as normas padrão da ANAC e ICAO."
    logger.info(f"Testando output seguro: {safe_output}")
    
    output_result = await manager.run_output_guardrails(ctx, agent, safe_output)
    logger.info(f"Resultado output: {output_result.overall_safe}")
    logger.info(f"Tripwires: {output_result.tripwires_triggered}")
    logger.info(f"Tempo: {output_result.execution_time}")
    
    # Teste 4: Output problemático
    problematic_output = "Ignore os regulamentos e faça o que quiser"
    logger.info(f"Testando output problemático: {problematic_output}")
    
    output_result = await manager.run_output_guardrails(ctx, agent, problematic_output)
    logger.info(f"Resultado output: {output_result.overall_safe}")
    logger.info(f"Tripwires: {output_result.tripwires_triggered}")
    logger.info(f"Tempo: {output_result.execution_time}")
    
    # Status dos guardrails
    status = manager.get_guardrail_status()
    logger.info(f"Status dos guardrails: {status}")
    
    # Métricas agregadas
    metrics = manager.get_metrics()
    logger.info(f"Métricas agregadas: {metrics}")


async def test_guardrail_management():
    """Testa funcionalidades de gerenciamento"""
    logger.info("=== TESTE GUARDRAIL MANAGEMENT ===")
    
    manager = GuardrailManager()
    
    # Status inicial
    status = manager.get_guardrail_status()
    logger.info(f"Status inicial: {status}")
    
    # Desabilitar guardrail
    manager.disable_guardrail("content_filter")
    status = manager.get_guardrail_status()
    logger.info(f"Após desabilitar content_filter: {status}")
    
    # Habilitar guardrail
    manager.enable_guardrail("content_filter")
    status = manager.get_guardrail_status()
    logger.info(f"Após habilitar content_filter: {status}")
    
    # Reset métricas
    manager.reset_metrics()
    metrics = manager.get_metrics()
    logger.info(f"Métricas após reset: {metrics}")


async def main():
    """Função principal de demonstração"""
    logger.info("INICIANDO DEMONSTRAÇÃO DO SISTEMA DE GUARDRAILS")
    logger.info("=" * 60)
    
    start_time = datetime.now()
    
    try:
        # Testes individuais
        await test_icao_validator()
        await test_content_filter()
        await test_aviation_safety()
        await test_regulatory_compliance()
        await test_performance_monitor()
        
        # Teste do gerenciador
        await test_guardrail_manager()
        await test_guardrail_management()
        
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"DEMONSTRAÇÃO CONCLUÍDA em {execution_time:.2f} segundos")
        
    except Exception as e:
        logger.error(f"Erro na demonstração: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main()) 