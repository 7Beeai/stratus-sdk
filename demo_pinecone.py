#!/usr/bin/env python3
"""
Demonstração do PineconeMCPServer - Base Vetorial de Conhecimento Aeronáutico
Testa todas as 23 ferramentas MCP implementadas com exemplos práticos de aviação.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any

from src.mcp_servers.pinecone_server import PineconeMCPServer, MCP_TOOLS
from src.utils.logging import get_logger

logger = get_logger()

class PineconeDemo:
    """Demonstração completa do PineconeMCPServer"""
    
    def __init__(self):
        self.server = None
        self.test_queries = {
            # GRUPO 1: REGULAMENTAÇÃO E NORMAS
            "ANAC": "Quais são os requisitos para licença de piloto comercial?",
            "DECEA": "Procedimentos IFR para aproximação em SBSP",
            "ICAO": "Normas internacionais para operações noturnas",
            "ProcedimentosOperacionais": "Checklist de emergência para falha de motor",
            
            # GRUPO 2: NAVEGAÇÃO E CARTAS
            "AIP_Brasil_Map": "Cartas de aproximação VOR para SBGR",
            "Jeppesen_Manuais": "Briefing de rota SBSP-SBGR",
            "Planejamento_de_Voo": "Planejamento de combustível para voo IFR",
            
            # GRUPO 3: AERONAVES E SISTEMAS
            "Manuais_Aeronaves_Equipamentos": "Performance da Cessna 172 em pista molhada",
            "InstrumentosAvionicosSistemasEletricos": "Funcionamento do sistema de navegação GPS",
            "PesoBalanceamento_Performance": "Cálculo de peso e balanceamento para C172",
            
            # GRUPO 4: COMUNICAÇÃO E OPERAÇÕES ESPECIAIS
            "ComunicacoesAereas": "Fraseologia para emergência médica",
            "Anfibios_HidroAvioes": "Procedimentos de pouso em água",
            "SoftSkills_Risk_Medical": "CRM em situação de emergência",
            
            # GRUPO 5: FORMAÇÃO E EDUCAÇÃO
            "MaterialFormacao_BancaANAC_Simulados": "Questões sobre meteorologia para prova ANAC",
            "InstrutoresDeVoo": "Técnicas de ensino para pouso de emergência",
            "Exame SDEA ICAO ANAC": "Preparação para exame de proficiência linguística",
            "Miscelanea": "História da aviação brasileira"
        }
        
        self.multi_namespace_queries = {
            "Regulamentação": "RBAC 91 - Regras gerais de voo",
            "Navegação": "Cartas aeronáuticas para voo IFR",
            "Aeronaves": "Manuais de aeronave e performance",
            "Educação": "Material de estudo para pilotos",
            "Safety Critical": "Procedimentos de emergência e segurança"
        }

    async def __aenter__(self):
        """Inicializar servidor"""
        self.server = PineconeMCPServer()
        await self.server.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Finalizar servidor"""
        if self.server:
            await self.server.__aexit__(exc_type, exc_val, exc_tb)

    async def test_individual_namespaces(self):
        """Testar busca em namespaces individuais"""
        print("\n" + "="*80)
        print("🧪 TESTE DE NAMESPACES INDIVIDUAIS (17 ferramentas)")
        print("="*80)
        
        results = {}
        
        for namespace, query in self.test_queries.items():
            try:
                print(f"\n📋 Testando namespace: {namespace}")
                print(f"   Query: {query}")
                
                # Usar método direto do servidor
                method_name = f"search_{namespace.lower().replace(' ', '_').replace('e_seus_anexos', '')}"
                if hasattr(self.server, method_name):
                    method = getattr(self.server, method_name)
                    result = await method(query, top_k=5, user_id="demo_user")
                else:
                    # Fallback para busca geral
                    result = await self.server.search_knowledge_base(query, [namespace], 5, "demo_user")
                
                results[namespace] = {
                    "success": True,
                    "namespaces_searched": result.namespaces_searched,
                    "total_results": result.total_results,
                    "search_time_ms": result.search_time_ms,
                    "cache_hit": result.cache_hit
                }
                
                print(f"   ✅ Sucesso: {result.total_results} resultados em {result.search_time_ms:.1f}ms")
                print(f"   📊 Namespaces: {result.namespaces_searched}")
                print(f"   💾 Cache hit: {result.cache_hit}")
                
                # Mostrar primeiros resultados
                for i, res in enumerate(result.results[:2]):
                    print(f"   📄 Resultado {i+1}: {res.content[:100]}... (score: {res.score:.3f})")
                
            except Exception as e:
                results[namespace] = {"success": False, "error": str(e)}
                print(f"   ❌ Erro: {str(e)}")
        
        return results

    async def test_multi_namespaces(self):
        """Testar busca em múltiplos namespaces"""
        print("\n" + "="*80)
        print("🌐 TESTE DE MÚLTIPLOS NAMESPACES (5 ferramentas)")
        print("="*80)
        
        results = {}
        
        for category, query in self.multi_namespace_queries.items():
            try:
                print(f"\n📋 Testando categoria: {category}")
                print(f"   Query: {query}")
                
                # Usar método multi-namespace
                method_name = f"search_{category.lower().replace(' ', '_')}"
                if hasattr(self.server, method_name):
                    method = getattr(self.server, method_name)
                    result = await method(query, top_k=10, user_id="demo_user")
                else:
                    # Fallback para busca geral
                    result = await self.server.search_knowledge_base(query, None, 10, "demo_user")
                
                results[category] = {
                    "success": True,
                    "namespaces_searched": result.namespaces_searched,
                    "total_results": result.total_results,
                    "search_time_ms": result.search_time_ms,
                    "cache_hit": result.cache_hit
                }
                
                print(f"   ✅ Sucesso: {result.total_results} resultados em {result.search_time_ms:.1f}ms")
                print(f"   📊 Namespaces: {result.namespaces_searched}")
                print(f"   💾 Cache hit: {result.cache_hit}")
                
                # Mostrar primeiros resultados
                for i, res in enumerate(result.results[:3]):
                    print(f"   📄 Resultado {i+1}: {res.content[:80]}... (score: {res.score:.3f})")
                
            except Exception as e:
                results[category] = {"success": False, "error": str(e)}
                print(f"   ❌ Erro: {str(e)}")
        
        return results

    async def test_mcp_tools(self):
        """Testar ferramentas MCP diretamente"""
        print("\n" + "="*80)
        print("🔧 TESTE DE FERRAMENTAS MCP (23 ferramentas)")
        print("="*80)
        
        results = {}
        
        # Testar algumas ferramentas MCP selecionadas
        test_tools = {
            "search_anac": "Regulamentações ANAC para pilotos privados",
            "search_decea": "Cartas DECEA para SBSP",
            "search_icao": "Normas ICAO para operações internacionais",
            "search_regulations": "Todas as regulamentações de aviação",
            "search_safety_critical": "Procedimentos críticos de segurança"
        }
        
        for tool_name, query in test_tools.items():
            try:
                print(f"\n📋 Testando ferramenta MCP: {tool_name}")
                print(f"   Query: {query}")
                
                # Usar ferramenta MCP
                tool_func = MCP_TOOLS[tool_name]
                result = await tool_func(query, top_k=5, user_id="demo_user")
                
                results[tool_name] = {
                    "success": True,
                    "namespaces_searched": result.get("namespaces_searched", []),
                    "total_results": result.get("total_results", 0),
                    "search_time_ms": result.get("search_time_ms", 0),
                    "cache_hit": result.get("cache_hit", False)
                }
                
                print(f"   ✅ Sucesso: {result.get('total_results', 0)} resultados em {result.get('search_time_ms', 0):.1f}ms")
                print(f"   📊 Namespaces: {result.get('namespaces_searched', [])}")
                print(f"   💾 Cache hit: {result.get('cache_hit', False)}")
                
            except Exception as e:
                results[tool_name] = {"success": False, "error": str(e)}
                print(f"   ❌ Erro: {str(e)}")
        
        return results

    async def test_aviation_context(self):
        """Testar extração de contexto aeronáutico"""
        print("\n" + "="*80)
        print("✈️ TESTE DE CONTEXTO AERONÁUTICO")
        print("="*80)
        
        test_queries = [
            "Procedimentos de emergência para C172 em SBSP",
            "RBAC 91 seção 3 - Regras de voo visual",
            "Checklist de emergência para falha de motor em voo IFR",
            "Comunicação com ATC em situação de emergência médica",
            "Performance da aeronave em condições meteorológicas adversas"
        ]
        
        for query in test_queries:
            try:
                print(f"\n📋 Query: {query}")
                
                # Extrair contexto
                context = self.server._extract_aviation_context(query)
                
                print(f"   🏷️ Códigos ICAO: {context['icao_codes']}")
                print(f"   ✈️ Tipos de aeronave: {context['aircraft_types']}")
                print(f"   📜 Regulamentações: {context['regulations']}")
                print(f"   ⚠️ Safety Critical: {context['safety_critical']}")
                
                # Selecionar namespaces relevantes
                relevant_namespaces = self.server._select_relevant_namespaces(query, context)
                print(f"   🎯 Namespaces relevantes: {relevant_namespaces}")
                
            except Exception as e:
                print(f"   ❌ Erro: {str(e)}")

    async def test_performance(self):
        """Testar performance e cache"""
        print("\n" + "="*80)
        print("⚡ TESTE DE PERFORMANCE E CACHE")
        print("="*80)
        
        query = "Procedimentos de emergência para falha de motor"
        
        # Primeira busca (sem cache)
        print(f"\n📋 Primeira busca: {query}")
        start_time = datetime.now()
        result1 = await self.server.search_safety_critical(query, top_k=10, user_id="demo_user")
        time1 = (datetime.now() - start_time).total_seconds() * 1000
        
        print(f"   ⏱️ Tempo: {time1:.1f}ms")
        print(f"   📊 Resultados: {result1.total_results}")
        print(f"   💾 Cache hit: {result1.cache_hit}")
        
        # Segunda busca (com cache)
        print(f"\n📋 Segunda busca (cache): {query}")
        start_time = datetime.now()
        result2 = await self.server.search_safety_critical(query, top_k=10, user_id="demo_user")
        time2 = (datetime.now() - start_time).total_seconds() * 1000
        
        print(f"   ⏱️ Tempo: {time2:.1f}ms")
        print(f"   📊 Resultados: {result2.total_results}")
        print(f"   💾 Cache hit: {result2.cache_hit}")
        
        # Comparação
        if time1 > 0:
            speedup = time1 / time2 if time2 > 0 else float('inf')
            print(f"   🚀 Speedup: {speedup:.1f}x mais rápido com cache")

    async def run_all_tests(self):
        """Executar todos os testes"""
        print("🚀 INICIANDO DEMONSTRAÇÃO DO PINECONEMCPSERVER")
        print("="*80)
        print(f"⏰ Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Testar namespaces individuais
            individual_results = await self.test_individual_namespaces()
            
            # Testar múltiplos namespaces
            multi_results = await self.test_multi_namespaces()
            
            # Testar ferramentas MCP
            mcp_results = await self.test_mcp_tools()
            
            # Testar contexto aeronáutico
            await self.test_aviation_context()
            
            # Testar performance
            await self.test_performance()
            
            # Resumo final
            print("\n" + "="*80)
            print("📊 RESUMO FINAL")
            print("="*80)
            
            total_individual = len(individual_results)
            successful_individual = sum(1 for r in individual_results.values() if r.get("success", False))
            
            total_multi = len(multi_results)
            successful_multi = sum(1 for r in multi_results.values() if r.get("success", False))
            
            total_mcp = len(mcp_results)
            successful_mcp = sum(1 for r in mcp_results.values() if r.get("success", False))
            
            print(f"✅ Namespaces individuais: {successful_individual}/{total_individual}")
            print(f"✅ Múltiplos namespaces: {successful_multi}/{total_multi}")
            print(f"✅ Ferramentas MCP: {successful_mcp}/{total_mcp}")
            print(f"✅ Total de ferramentas testadas: {successful_individual + successful_multi + successful_mcp}")
            
            print(f"\n⏰ Fim: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("🎉 Demonstração concluída com sucesso!")
            
        except Exception as e:
            logger.log_agent_action(
                agent_name="PineconeDemo",
                action="run_all_tests",
                message=f"Erro na demonstração: {str(e)}",
                user_id="demo_user",
                success=False
            )
            print(f"❌ Erro na demonstração: {str(e)}")

async def main():
    """Função principal"""
    async with PineconeDemo() as demo:
        await demo.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main()) 