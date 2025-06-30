#!/usr/bin/env python3
"""
Teste simples das configurações do Stratus.IA
"""

import os
import sys

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_config():
    """Testar carregamento das configurações."""
    try:
        from config.settings import settings
        from src.utils.base import get_logger, validate_icao_code
        
        print("✅ Configurações carregadas com sucesso!")
        print(f"   Ambiente: {settings.environment}")
        print(f"   Log Level: {settings.log_level}")
        print(f"   Max Response Time: {settings.max_response_time}s")
        
        # Testar logger
        logger = get_logger("test")
        logger.info("Teste de logging estruturado", test=True)
        
        # Testar validação ICAO
        assert validate_icao_code("SBGR") == True
        assert validate_icao_code("INVALID") == False
        print("✅ Validações ICAO funcionando!")
        
        print("\n🎯 Configurações críticas:")
        print(f"   OpenAI API Key: {'✅ Configurada' if settings.openai_api_key else '❌ Não configurada'}")
        print(f"   Pinecone API Key: {'✅ Configurada' if settings.pinecone_api_key else '❌ Não configurada'}")
        print(f"   Pinecone Environment: {'✅ Configurado' if settings.pinecone_environment else '❌ Não configurado'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao testar configurações: {e}")
        return False

if __name__ == "__main__":
    success = test_config()
    sys.exit(0 if success else 1) 