#!/usr/bin/env python3
"""
Teste da API Stratus.IA
Verifica se a API está funcionando corretamente
"""

import asyncio
import httpx
import json
from datetime import datetime

# Configurações
BASE_URL = "http://localhost:8000"
TEST_USER = {
    "name": "Teste Usuário",
    "email": "teste@stratus.ia",
    "password": "Teste123!",
    "role": "pilot",
    "licenses": ["PP", "PC"],
    "experience_level": "Intermediário"
}

async def test_health_check():
    """Testa health check da API"""
    print("🏥 Testando Health Check...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health Check OK - Status: {data.get('status')}")
                print(f"   Versão: {data.get('version')}")
                print(f"   Uptime: {data.get('uptime'):.2f}s")
                return True
            else:
                print(f"❌ Health Check falhou - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Erro no Health Check: {e}")
            return False

async def test_info():
    """Testa endpoint de informações"""
    print("\n📋 Testando Info...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/info")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Info OK - {data.get('name')} v{data.get('version')}")
                return True
            else:
                print(f"❌ Info falhou - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Erro no Info: {e}")
            return False

async def test_register():
    """Testa registro de usuário"""
    print("\n👤 Testando Registro...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/auth/register",
                json=TEST_USER
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Registro OK - User ID: {data.get('user_id')}")
                return data.get('access_token')
            else:
                print(f"❌ Registro falhou - Status: {response.status_code}")
                print(f"   Resposta: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Erro no Registro: {e}")
            return None

async def test_login():
    """Testa login de usuário"""
    print("\n🔐 Testando Login...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/auth/login",
                json={
                    "email": TEST_USER["email"],
                    "password": TEST_USER["password"]
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Login OK - Role: {data.get('role')}")
                return data.get('access_token')
            else:
                print(f"❌ Login falhou - Status: {response.status_code}")
                print(f"   Resposta: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Erro no Login: {e}")
            return None

async def test_chat(token):
    """Testa chat com autenticação"""
    print("\n💬 Testando Chat...")
    
    if not token:
        print("❌ Token não disponível para teste de chat")
        return False
    
    async with httpx.AsyncClient() as client:
        try:
            headers = {"Authorization": f"Bearer {token}"}
            
            response = await client.post(
                f"{BASE_URL}/chat",
                json={
                    "message": "Olá! Como está o tempo para voo hoje?",
                    "message_type": "question",
                    "context": {"airport": "SBSP"}
                },
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Chat OK - Agente: {data.get('agent_name')}")
                print(f"   Resposta: {data.get('response')[:100]}...")
                print(f"   Tempo: {data.get('processing_time'):.3f}s")
                return True
            else:
                print(f"❌ Chat falhou - Status: {response.status_code}")
                print(f"   Resposta: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Erro no Chat: {e}")
            return False

async def test_metrics():
    """Testa endpoint de métricas"""
    print("\n📊 Testando Métricas...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/metrics")
            if response.status_code == 200:
                print("✅ Métricas OK")
                return True
            else:
                print(f"❌ Métricas falharam - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Erro nas Métricas: {e}")
            return False

async def main():
    """Função principal de teste"""
    print("🚀 Iniciando Testes da API Stratus.IA")
    print("=" * 50)
    
    # Testa endpoints básicos
    health_ok = await test_health_check()
    info_ok = await test_info()
    
    if not health_ok:
        print("\n❌ API não está respondendo. Verifique se está rodando em http://localhost:8000")
        return
    
    # Testa autenticação
    token = await test_register()
    if not token:
        token = await test_login()  # Tenta login se registro falhou
    
    # Testa funcionalidades autenticadas
    if token:
        chat_ok = await test_chat(token)
    else:
        chat_ok = False
    
    # Testa métricas
    metrics_ok = await test_metrics()
    
    # Resumo
    print("\n" + "=" * 50)
    print("📋 RESUMO DOS TESTES")
    print("=" * 50)
    print(f"Health Check: {'✅' if health_ok else '❌'}")
    print(f"Info: {'✅' if info_ok else '❌'}")
    print(f"Autenticação: {'✅' if token else '❌'}")
    print(f"Chat: {'✅' if chat_ok else '❌'}")
    print(f"Métricas: {'✅' if metrics_ok else '❌'}")
    
    if all([health_ok, info_ok, token, chat_ok, metrics_ok]):
        print("\n🎉 Todos os testes passaram! API funcionando corretamente.")
    else:
        print("\n⚠️ Alguns testes falharam. Verifique os logs acima.")

if __name__ == "__main__":
    asyncio.run(main()) 