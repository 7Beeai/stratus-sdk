#!/usr/bin/env python3
"""
Script para configurar arquivo .env para produção
"""

import os
import shutil

def setup_env():
    """Configura o arquivo .env para produção"""
    
    print("🔧 Configurando arquivo .env para produção...")
    
    # Copia o arquivo de exemplo
    if os.path.exists('env.example'):
        shutil.copy('env.example', '.env')
        print("✅ Arquivo .env criado baseado no env.example")
    else:
        print("❌ Arquivo env.example não encontrado")
        return False
    
    # Configurações específicas para produção
    env_updates = {
        'ENVIRONMENT': 'production',
        'API_WORKERS': '1',
        'CORS_ORIGINS': 'https://api.stratus.7bee.ai,https://stratus.7bee.ai',
        'TRUSTED_HOSTS': 'api.stratus.7bee.ai,stratus.7bee.ai',
        'USE_GOOGLE_SECRET_MANAGER': 'true',
        'GOOGLE_CLOUD_PROJECT': '7bee-ai',
        'GOOGLE_CLOUD_REGION': 'us-central1'
    }
    
    # Lê o arquivo .env
    with open('.env', 'r') as f:
        content = f.read()
    
    # Aplica as atualizações
    for key, value in env_updates.items():
        # Substitui a linha se existir, ou adiciona no final
        if f'{key}=' in content:
            content = content.replace(f'{key}=', f'{key}={value}')
        else:
            content += f'\n{key}={value}'
    
    # Escreve o arquivo atualizado
    with open('.env', 'w') as f:
        f.write(content)
    
    print("✅ Configurações de produção aplicadas")
    print("\n📋 Próximos passos:")
    print("1. Edite o arquivo .env e configure suas chaves:")
    print("   - OPENAI_API_KEY")
    print("   - JWT_SECRET")
    print("   - PINECONE_API_KEY (se necessário)")
    print("   - Outras chaves de API conforme necessário")
    print("\n2. Execute o deploy:")
    print("   ./deploy.sh")
    
    return True

if __name__ == "__main__":
    setup_env() 