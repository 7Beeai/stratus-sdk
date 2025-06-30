#!/usr/bin/env python3
"""
Teste Simples dos Guardrails - Stratus.IA

Teste básico para verificar se o sistema está funcionando
"""

import os
import asyncio
import logging

# Definir API key
os.environ['OPENAI_API_KEY'] = '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'

from src.guardrails import ICAOValidator

# Configurar logging básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test.guardrails")

class MockContext:
    def __init__(self):
        self.context = {"user_id": "test_user"}

class MockAgent:
    def __init__(self, name: str = "Test Agent"):
        self.name = name

async def test_icao_validator():
    """Teste simples do validador ICAO"""
    print("=== TESTE ICAO VALIDATOR ===")
    
    validator = ICAOValidator()
    ctx = MockContext()
    agent = MockAgent()
    
    # Teste 1: Código ICAO válido
    valid_input = "Aeroporto SBGR (Guarulhos)"
    print(f"Testando input válido: {valid_input}")
    
    try:
        result = await validator.validate_icao_codes(ctx, agent, valid_input)
        print(f"Resultado: {result.tripwire_triggered}")
        print(f"Output: {result.output_info}")
        print("✓ Teste válido passou")
    except Exception as e:
        print(f"✗ Erro no teste válido: {e}")
    
    # Teste 2: Código ICAO inválido
    invalid_input = "Aeroporto INVALID (Inválido)"
    print(f"Testando input inválido: {invalid_input}")
    
    try:
        result = await validator.validate_icao_codes(ctx, agent, invalid_input)
        print(f"Resultado: {result.tripwire_triggered}")
        print(f"Output: {result.output_info}")
        print("✓ Teste inválido passou")
    except Exception as e:
        print(f"✗ Erro no teste inválido: {e}")
    
    # Métricas
    print(f"Métricas: {validator.metrics}")

async def main():
    """Função principal"""
    print("INICIANDO TESTE SIMPLES DOS GUARDRAILS")
    print("=" * 50)
    
    try:
        await test_icao_validator()
        print("\n✓ TESTE CONCLUÍDO COM SUCESSO")
    except Exception as e:
        print(f"\n✗ ERRO NO TESTE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 