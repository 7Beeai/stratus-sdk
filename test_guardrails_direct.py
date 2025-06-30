#!/usr/bin/env python3
"""
Teste Direto dos Guardrails - Stratus.IA

Teste sem configuração complexa de logging
"""

import os
import asyncio
import logging

# Definir API key
os.environ['OPENAI_API_KEY'] = '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'

# Configurar logging básico
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

from src.guardrails import (
    ICAOValidator,
    ContentFilter,
    AviationSafety,
    RegulatoryCompliance,
    PerformanceMonitor,
    GuardrailManager
)

class MockContext:
    def __init__(self):
        self.context = {"user_id": "test_user"}
        self.guardrails = None

class MockAgent:
    def __init__(self, name: str = "Test Agent"):
        self.name = name

async def test_individual_components():
    """Testa componentes individuais"""
    print("=== TESTE COMPONENTES INDIVIDUAIS ===")
    
    ctx = MockContext()
    agent = MockAgent()
    
    # Teste ICAOValidator
    print("\n1. Testando ICAOValidator...")
    validator = ICAOValidator()
    result = await validator.validate_icao_codes(ctx, agent, "Aeroporto SBGR")
    print(f"   Resultado: {result.tripwire_triggered}")
    
    # Teste ContentFilter (pode demorar)
    print("\n2. Testando ContentFilter...")
    try:
        filter_obj = ContentFilter()
        result = await filter_obj.filter_input_content(ctx, agent, "Teste de conteúdo")
        print(f"   Resultado: {result.tripwire_triggered}")
    except Exception as e:
        print(f"   Erro: {e}")
    
    # Teste AviationSafety (pode demorar)
    print("\n3. Testando AviationSafety...")
    try:
        safety = AviationSafety()
        result = await safety.check_aviation_safety(ctx, agent, "Procedimento seguro")
        print(f"   Resultado: {result.tripwire_triggered}")
    except Exception as e:
        print(f"   Erro: {e}")
    
    # Teste RegulatoryCompliance (pode demorar)
    print("\n4. Testando RegulatoryCompliance...")
    try:
        compliance = RegulatoryCompliance()
        result = await compliance.check_compliance(ctx, agent, "Procedimento conforme")
        print(f"   Resultado: {result.tripwire_triggered}")
    except Exception as e:
        print(f"   Erro: {e}")
    
    # Teste PerformanceMonitor (pode demorar)
    print("\n5. Testando PerformanceMonitor...")
    try:
        monitor = PerformanceMonitor()
        result = await monitor.monitor_performance(ctx, agent, "Resposta de qualidade")
        print(f"   Resultado: {result.tripwire_triggered}")
    except Exception as e:
        print(f"   Erro: {e}")

async def test_guardrail_manager():
    """Testa o gerenciador de guardrails"""
    print("\n=== TESTE GUARDRAIL MANAGER ===")
    
    manager = GuardrailManager()
    ctx = MockContext()
    ctx.guardrails = manager
    agent = MockAgent()
    
    # Teste input seguro
    print("\n1. Testando input seguro...")
    try:
        result = await manager.run_input_guardrails(ctx, agent, "Qual é o procedimento de pouso em SBGR?")
        print(f"   Resultado: {result.overall_safe}")
        print(f"   Tripwires: {result.tripwires_triggered}")
    except Exception as e:
        print(f"   Erro: {e}")
    
    # Teste output seguro
    print("\n2. Testando output seguro...")
    try:
        result = await manager.run_output_guardrails(ctx, agent, "O procedimento de pouso em SBGR segue as normas.")
        print(f"   Resultado: {result.overall_safe}")
        print(f"   Tripwires: {result.tripwires_triggered}")
    except Exception as e:
        print(f"   Erro: {e}")

async def main():
    """Função principal"""
    print("INICIANDO TESTE DIRETO DOS GUARDRAILS")
    print("=" * 50)
    
    try:
        await test_individual_components()
        await test_guardrail_manager()
        print("\n✓ TESTE CONCLUÍDO COM SUCESSO")
    except Exception as e:
        print(f"\n✗ ERRO NO TESTE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 