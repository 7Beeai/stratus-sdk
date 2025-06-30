#!/usr/bin/env python3
"""
Demonstração dos Agentes Router e Orchestrator do Stratus.IA
Testa classificação, roteamento e síntese de respostas para todas as categorias
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any

from src.agents.router import StratusRouterAgent, MessageCategory, UrgencyLevel
from src.agents.orchestrator import StratusOrchestratorAgent
from src.utils.logging import get_logger

logger = get_logger()

class AgentsDemo:
    """Demonstração completa dos agentes Router e Orchestrator"""
    
    def __init__(self):
        self.router = StratusRouterAgent()
        self.orchestrator = StratusOrchestratorAgent()
        self.results = {}
        self.start_time = None
        self.end_time = None
    
    def get_test_messages(self) -> Dict[str, str]:
        """Retorna mensagens de teste para todas as categorias"""
        return {
            "regulatory": "Qual é o RBAC 91 sobre decolagem com vento de cauda?",
            "technical": "Quais são os procedimentos de emergência do B737-800 no QRH?",
            "weather": "Preciso do METAR e TAF para SBGR e SBSP para planejamento de voo",
            "geographic": "Quais são as coordenadas e elevação do aeródromo SBFL?",
            "performance": "Como calcular o peso máximo de decolagem do A320?",
            "operations": "Planejo voar SBGR-SBBR amanhã, preciso de rota e combustível",
            "education": "Quais são os requisitos para licença de piloto comercial?",
            "communication": "O que significa a fraseologia 'cleared for takeoff'?",
            "social": "Olá! Como vai o Stratus.IA hoje?"
        }
    
    async def test_router_classification(self):
        """Testa classificação de mensagens pelo Router"""
        print("\n" + "="*60)
        print("🧠 TESTANDO ROUTER AGENT - CLASSIFICAÇÃO")
        print("="*60)
        
        test_messages = self.get_test_messages()
        
        for category_name, message in test_messages.items():
            print(f"\n📝 Testando categoria: {category_name.upper()}")
            print(f"   Mensagem: {message}")
            
            start = time.time()
            classification = await self.router.route_message(message, "demo_user")
            response_time = (time.time() - start) * 1000
            
            print(f"   ✅ Categoria detectada: {classification.primary_category.value}")
            print(f"   🎯 Confiança: {classification.confidence:.2f}")
            print(f"   ⚡ Urgência: {classification.urgency.value}")
            print(f"   🤖 Agentes recomendados: {classification.recommended_agents}")
            print(f"   📍 Entidades: ICAO={classification.entities['icao_codes']}")
            print(f"   ⏱️ Tempo: {response_time:.2f}ms")
            
            # Validar se a classificação está correta
            expected_category = getattr(MessageCategory, category_name.upper())
            is_correct = classification.primary_category == expected_category
            
            print(f"   {'✅ CORRETO' if is_correct else '❌ INCORRETO'}")
            
            self.results[f"router_{category_name}"] = {
                'status': 'success' if is_correct else 'error',
                'expected': expected_category.value,
                'detected': classification.primary_category.value,
                'confidence': classification.confidence,
                'response_time_ms': response_time,
                'is_correct': is_correct
            }
    
    async def test_entity_extraction(self):
        """Testa extração de entidades pelo Router"""
        print("\n" + "="*60)
        print("🔍 TESTANDO EXTRAÇÃO DE ENTIDADES")
        print("="*60)
        
        test_cases = [
            ("METAR SBGR 271200Z 08010KT 9999 SCT030 BKN100 25/15 Q1018", ["SBGR"]),
            ("Voo SBGR-SBSP com B737-800", ["SBGR", "SBSP"], ["B737"]),
            ("RBAC 91 seção 91.103 sobre planejamento de voo", ["RBAC 91"]),
            ("NOTAM A1234/24 para SBFL", ["SBFL"]),
            ("TAF SBSP 271200Z 2712/2812 08010KT 9999 SCT030", ["SBSP"])
        ]
        
        for i, (message, expected_icao, *expected_others) in enumerate(test_cases, 1):
            print(f"\n🔍 Teste {i}: {message}")
            
            entities = self.router.extract_entities(message)
            
            print(f"   📍 ICAO extraídos: {entities.icao_codes}")
            print(f"   ✈️ Aeronaves: {entities.aircraft_types}")
            print(f"   📋 Regulamentações: {entities.regulations}")
            print(f"   🌤️ Termos meteorológicos: {entities.weather_terms}")
            
            # Validar extração
            icao_correct = set(entities.icao_codes) == set(expected_icao)
            print(f"   {'✅ ICAO CORRETO' if icao_correct else '❌ ICAO INCORRETO'}")
            
            if expected_others:
                aircraft_expected = expected_others[0] if expected_others[0] else []
                aircraft_correct = set(entities.aircraft_types) == set(aircraft_expected)
                print(f"   {'✅ AERONAVES CORRETO' if aircraft_correct else '❌ AERONAVES INCORRETO'}")
    
    async def test_urgency_detection(self):
        """Testa detecção de urgência pelo Router"""
        print("\n" + "="*60)
        print("🚨 TESTANDO DETECÇÃO DE URGÊNCIA")
        print("="*60)
        
        test_cases = [
            ("MAYDAY MAYDAY MAYDAY", UrgencyLevel.EMERGENCY),
            ("PAN-PAN PAN-PAN PAN-PAN", UrgencyLevel.EMERGENCY),
            ("URGENTE: Falha no motor", UrgencyLevel.URGENT),
            ("CRÍTICO: NOTAM para pista", UrgencyLevel.URGENT),
            ("Planejamento de voo SBGR-SBBR", UrgencyLevel.HIGH),
            ("METAR e TAF para SBSP", UrgencyLevel.HIGH),
            ("Como calcular performance", UrgencyLevel.NORMAL),
            ("O que significa RBAC", UrgencyLevel.NORMAL),
            ("Olá, tudo bem?", UrgencyLevel.LOW),
            ("Obrigado pela ajuda", UrgencyLevel.LOW)
        ]
        
        for message, expected_urgency in test_cases:
            print(f"\n🚨 Teste: {message}")
            
            entities = self.router.extract_entities(message)
            detected_urgency = self.router.determine_urgency(message, entities)
            
            print(f"   ⚡ Urgência detectada: {detected_urgency.value}")
            print(f"   🎯 Urgência esperada: {expected_urgency.value}")
            
            is_correct = detected_urgency == expected_urgency
            print(f"   {'✅ CORRETO' if is_correct else '❌ INCORRETO'}")
    
    async def test_orchestrator_synthesis(self):
        """Testa síntese de respostas pelo Orchestrator"""
        print("\n" + "="*60)
        print("🎼 TESTANDO ORCHESTRATOR AGENT - SÍNTESE")
        print("="*60)
        
        # Testar com diferentes categorias
        test_cases = [
            ("regulatory", "Qual é o RBAC 91 sobre decolagem?"),
            ("weather", "METAR para SBGR"),
            ("social", "Olá! Como vai?"),
            ("technical", "Procedimentos B737")
        ]
        
        for category_name, message in test_cases:
            print(f"\n🎼 Testando síntese: {category_name.upper()}")
            print(f"   Mensagem: {message}")
            
            # Primeiro classificar
            classification = await self.router.route_message(message, "demo_user")
            
            # Depois orquestrar
            start = time.time()
            response = await self.orchestrator.orchestrate(message, classification, "demo_user")
            response_time = (time.time() - start) * 1000
            
            print(f"   ✅ Categoria: {response.category}")
            print(f"   🤖 Agentes consultados: {response.agents_consulted}")
            print(f"   🎯 Confiança: {response.confidence:.2f}")
            print(f"   ⚠️ Warnings: {len(response.warning_messages)}")
            print(f"   📝 Requer confirmação: {response.requires_human_confirmation}")
            print(f"   ⏱️ Tempo: {response_time:.2f}ms")
            
            # Mostrar parte da resposta
            content_preview = response.content[:200] + "..." if len(response.content) > 200 else response.content
            print(f"   📄 Resposta: {content_preview}")
            
            self.results[f"orchestrator_{category_name}"] = {
                'status': 'success',
                'category': response.category,
                'agents_consulted': response.agents_consulted,
                'confidence': response.confidence,
                'response_time_ms': response_time,
                'requires_confirmation': response.requires_human_confirmation,
                'warnings_count': len(response.warning_messages)
            }
    
    async def test_complex_scenarios(self):
        """Testa cenários complexos com múltiplos agentes"""
        print("\n" + "="*60)
        print("🔄 TESTANDO CENÁRIOS COMPLEXOS")
        print("="*60)
        
        complex_messages = [
            "Preciso planejar voo SBGR-SBBR amanhã com B737-800, incluindo METAR, TAF, NOTAMs e cálculo de combustível",
            "Qual é o RBAC 91 sobre decolagem com vento de cauda e como calcular performance do A320?",
            "NOTAM para SBFL, METAR atual e regulamentação sobre pouso com chuva"
        ]
        
        for i, message in enumerate(complex_messages, 1):
            print(f"\n🔄 Cenário {i}: {message}")
            
            # Classificar
            classification = await self.router.route_message(message, "demo_user")
            
            print(f"   🎯 Categoria principal: {classification.primary_category.value}")
            print(f"   📋 Categorias secundárias: {[c.value for c in classification.secondary_categories]}")
            print(f"   🤖 Agentes recomendados: {classification.recommended_agents}")
            print(f"   ⚡ Urgência: {classification.urgency.value}")
            print(f"   📊 Complexidade: {classification.estimated_complexity}")
            
            # Orquestrar
            start = time.time()
            response = await self.orchestrator.orchestrate(message, classification, "demo_user")
            response_time = (time.time() - start) * 1000
            
            print(f"   ✅ Agentes executados: {len(response.agents_consulted)}")
            print(f"   🎯 Confiança final: {response.confidence:.2f}")
            print(f"   ⏱️ Tempo total: {response_time:.2f}ms")
            
            self.results[f"complex_scenario_{i}"] = {
                'status': 'success',
                'primary_category': classification.primary_category.value,
                'secondary_categories': [c.value for c in classification.secondary_categories],
                'agents_count': len(classification.recommended_agents),
                'complexity': classification.estimated_complexity,
                'response_time_ms': response_time,
                'final_confidence': response.confidence
            }
    
    async def run_all_tests(self):
        """Executa todos os testes"""
        print("🚀 INICIANDO DEMONSTRAÇÃO DOS AGENTES ROUTER E ORCHESTRATOR")
        print("="*80)
        
        self.start_time = datetime.now(timezone.utc)
        
        # Executar todos os testes
        await self.test_router_classification()
        await self.test_entity_extraction()
        await self.test_urgency_detection()
        await self.test_orchestrator_synthesis()
        await self.test_complex_scenarios()
        
        self.end_time = datetime.now(timezone.utc)
        
        # Relatório final
        await self.generate_report()
    
    async def generate_report(self):
        """Gera relatório final da demonstração"""
        print("\n" + "="*80)
        print("📊 RELATÓRIO FINAL DA DEMONSTRAÇÃO DOS AGENTES")
        print("="*80)
        
        total_duration = (self.end_time - self.start_time).total_seconds()
        
        print(f"\n⏱️ Tempo total de execução: {total_duration:.2f} segundos")
        print(f"🕐 Início: {self.start_time.strftime('%H:%M:%S')}")
        print(f"🕐 Fim: {self.end_time.strftime('%H:%M:%S')}")
        
        # Estatísticas do Router
        router_tests = [k for k in self.results.keys() if k.startswith('router_')]
        router_correct = sum(1 for k in router_tests if self.results[k].get('is_correct', False))
        router_total = len(router_tests)
        
        print(f"\n🧠 ROUTER AGENT:")
        print(f"   ✅ Classificações corretas: {router_correct}/{router_total}")
        print(f"   📊 Taxa de acerto: {(router_correct/router_total)*100:.1f}%" if router_total > 0 else "   📊 Taxa de acerto: N/A")
        
        # Estatísticas do Orchestrator
        orchestrator_tests = [k for k in self.results.keys() if k.startswith('orchestrator_')]
        orchestrator_success = sum(1 for k in orchestrator_tests if self.results[k]['status'] == 'success')
        orchestrator_total = len(orchestrator_tests)
        
        print(f"\n🎼 ORCHESTRATOR AGENT:")
        print(f"   ✅ Sínteses bem-sucedidas: {orchestrator_success}/{orchestrator_total}")
        print(f"   📊 Taxa de sucesso: {(orchestrator_success/orchestrator_total)*100:.1f}%" if orchestrator_total > 0 else "   📊 Taxa de sucesso: N/A")
        
        # Estatísticas de performance
        router_times = [self.results[k]['response_time_ms'] for k in router_tests if 'response_time_ms' in self.results[k]]
        orchestrator_times = [self.results[k]['response_time_ms'] for k in orchestrator_tests if 'response_time_ms' in self.results[k]]
        
        if router_times:
            print(f"   ⚡ Tempo médio Router: {sum(router_times)/len(router_times):.2f}ms")
        if orchestrator_times:
            print(f"   ⚡ Tempo médio Orchestrator: {sum(orchestrator_times)/len(orchestrator_times):.2f}ms")
        
        # Cenários complexos
        complex_tests = [k for k in self.results.keys() if k.startswith('complex_scenario_')]
        if complex_tests:
            print(f"\n🔄 CENÁRIOS COMPLEXOS:")
            print(f"   📊 Cenários testados: {len(complex_tests)}")
            avg_agents = sum(self.results[k]['agents_count'] for k in complex_tests) / len(complex_tests)
            print(f"   🤖 Média de agentes por cenário: {avg_agents:.1f}")
            avg_time = sum(self.results[k]['response_time_ms'] for k in complex_tests) / len(complex_tests)
            print(f"   ⏱️ Tempo médio por cenário: {avg_time:.2f}ms")
        
        # Resumo geral
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results.values() if r['status'] == 'success')
        
        print(f"\n🎯 RESUMO GERAL:")
        print(f"   📊 Total de testes: {total_tests}")
        print(f"   ✅ Testes bem-sucedidos: {successful_tests}")
        print(f"   📈 Taxa de sucesso geral: {(successful_tests/total_tests)*100:.1f}%")
        
        if router_correct == router_total and orchestrator_success == orchestrator_total:
            print(f"\n🎉 TODOS OS AGENTES ESTÃO FUNCIONANDO PERFEITAMENTE!")
            print(f"🚀 Sistema pronto para integração com MCPs e produção!")
        else:
            print(f"\n⚠️ Alguns testes apresentaram problemas. Verificar logs para detalhes.")
        
        print(f"\n" + "="*80)

async def main():
    """Função principal"""
    demo = AgentsDemo()
    await demo.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main()) 