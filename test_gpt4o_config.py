#!/usr/bin/env python3
"""
Teste de Configuração GPT-4.1
Verifica se o modelo GPT-4.1 está configurado corretamente no sistema
"""

import asyncio
import os
import sys
from pathlib import Path

# Adiciona o diretório src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.settings import settings

async def test_gpt41_configuration():
    """Testa a configuração do modelo GPT-4.1"""
    print("🔧 Testando Configuração GPT-4.1")
    print("=" * 50)
    
    # Verifica configurações
    print(f"📋 Modelo OpenAI: {settings.openai_model}")
    print(f"🔑 API Key configurada: {'Sim' if settings.openai_api_key else 'Não'}")
    print(f"🎯 Max Tokens: {settings.openai_max_tokens}")
    print(f"🌡️  Temperature: {settings.openai_temperature}")
    
    # Verifica se o modelo está correto
    if settings.openai_model == "gpt-4.1":
        print("✅ Modelo GPT-4.1 configurado corretamente!")
    else:
        print(f"❌ Modelo incorreto: {settings.openai_model} (esperado: gpt-4.1)")
        return False
    
    # Verifica se a API key está configurada
    if not settings.openai_api_key:
        print("❌ API Key não configurada!")
        return False
    
    print("✅ API Key configurada!")
    
    print("\n🎉 Teste de configuração concluído com sucesso!")
    return True

async def main():
    """Função principal"""
    try:
        success = await test_gpt41_configuration()
        if success:
            print("\n✅ Sistema configurado corretamente para GPT-4.1!")
        else:
            print("\n❌ Problemas encontrados na configuração!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro no teste: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 