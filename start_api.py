#!/usr/bin/env python3
"""
Script para iniciar a API Stratus.IA
"""

import uvicorn
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

if __name__ == "__main__":
    # Configurações do servidor
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("DEBUG", "false").lower() == "true"
    
    print(f"🚀 Iniciando Stratus.IA API em http://{host}:{port}")
    print(f"📝 Debug mode: {reload}")
    print(f"🌍 Ambiente: {os.getenv('ENVIRONMENT', 'development')}")
    
    # Inicia o servidor
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    ) 