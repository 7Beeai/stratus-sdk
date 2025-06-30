#!/usr/bin/env python3
"""
Demonstração do Sistema de Handoffs do Stratus.IA
Testa delegação, consulta, escalação, colaboração, validação e MCPs.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any

from src.agents.handoffs import (
    HandoffManager, HandoffType, UrgencyLevel, MCPEnum,
    HandoffResult, HandoffError
)
from src.agents.auxiliary_agents import (
    WeatherAgent, RegulatoryAgent, PerformanceAgent, TechnicalAgent,
    EducationAgent, CommunicationAgent, GeographicAgent, OperationsAgent
)
from src.mcp_servers import (
    RedemetMCPServer, AISWEBMCPServer, PineconeMCPServer,
    AirportDBMCPServer, AviationWeatherGovMCPServer, ANACRegulationsMCPServer
)
from src.utils.logging import get_logger


class HandoffDemo:
    """Demonstração do sistema de handoffs."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.handoff_manager = HandoffManager()
        self.setup_agents()
        self.setup_mcps()
        
    def setup_agents(self):
        """Configura agentes para demonstração."""
        self.logger.info("Configurando agentes para demonstração...")
        
        # Cria instâncias dos agentes
        agents = {
            "weather": WeatherAgent(),
            "regulatory": RegulatoryAgent(),
            "performance": PerformanceAgent(),
            "technical": TechnicalAgent(),
            "education": EducationAgent(),
            "communication": CommunicationAgent(),
            "geographic": GeographicAgent(),
            "operations": OperationsAgent()
        }
        
        # Registra no HandoffManager
        for agent_id, agent in agents.items():
            self.handoff_manager.register_agent(agent_id, agent)
            self.logger.info(f"Agente registrado: {agent_id}")
        
        self.agents = agents
    
    def setup_mcps(self):
        """Configura MCPs para demonstração."""
        self.logger.info("Configurando MCPs para demonstração...")
        
        # Cria instâncias dos MCPs
        mcps = {
            MCPEnum.REDEMET: RedemetMCPServer(),
            MCPEnum.AISWEB: AISWEBMCPServer(),
            MCPEnum.PINECONE: PineconeMCPServer(),
            MCPEnum.AIRPORTDB: AirportDBMCPServer(),
            MCPEnum.WEATHER_APIS: AviationWeatherGovMCPServer(),
            MCPEnum.ANAC_REGULATIONS: ANACRegulationsMCPServer()
        }
        
        # Registra no HandoffManager
        for mcp_type, mcp in mcps.items():
            self.handoff_manager.register_mcp(mcp_type, mcp)
            self.logger.info(f"MCP registrado: {mcp_type.value}")
        
        self.mcps = mcps
    
    async def demo_delegation(self):
        """Demonstra delegação de tarefas."""
        self.logger.info("=== DEMONSTRAÇÃO: DELEGAÇÃO ===")
        
        # Cenário 1: Delegação simples
        context = {
            "message": "Preciso de informações meteorológicas para SBGR",
            "icao": "SBGR",
            "operation": "landing"
        }
        
        start_time = time.time()
        try:
            result = await self.handoff_manager.delegate("orchestrator", "weather", context)
            duration = time.time() - start_time
            
            self.logger.info(f"Delegação concluída em {duration:.3f}s")
            self.logger.info(f"Resultado: {result.data.get('response', 'N/A')[:100]}...")
            
        except HandoffError as e:
            self.logger.error(f"Erro na delegação: {e}")
        
        # Cenário 2: Delegação com timeout
        self.logger.info("\n--- Testando timeout ---")
        context2 = {
            "message": "Consulta complexa que pode demorar",
            "icao": "SBSP",
            "detailed": True
        }
        
        start_time = time.time()
        try:
            result = await self.handoff_manager.delegate("orchestrator", "weather", context2, timeout=0.1)
            duration = time.time() - start_time
            self.logger.info(f"Delegação concluída em {duration:.3f}s")
            
        except HandoffError as e:
            duration = time.time() - start_time
            self.logger.info(f"Timeout esperado em {duration:.3f}s: {e}")
    
    async def demo_consultation(self):
        """Demonstra consultas entre agentes."""
        self.logger.info("\n=== DEMONSTRAÇÃO: CONSULTA ===")
        
        # Cenário 1: Consulta regulamentar
        query = "Qual a regulamentação para pouso em SBGR com vento de 25 nós?"
        context = {
            "icao": "SBGR",
            "wind_speed": 25,
            "operation": "landing"
        }
        
        start_time = time.time()
        try:
            result = await self.handoff_manager.consult("weather", "regulatory", query, context)
            duration = time.time() - start_time
            
            self.logger.info(f"Consulta concluída em {duration:.3f}s")
            self.logger.info(f"Resposta: {result.data.get('response', 'N/A')[:100]}...")
            
        except HandoffError as e:
            self.logger.error(f"Erro na consulta: {e}")
        
        # Cenário 2: Consulta de performance
        query2 = "Qual a distância de pouso necessária para um Boeing 737 em SBGR?"
        context2 = {
            "aircraft": "B737",
            "icao": "SBGR",
            "runway": "09L"
        }
        
        start_time = time.time()
        try:
            result = await self.handoff_manager.consult("regulatory", "performance", query2, context2)
            duration = time.time() - start_time
            
            self.logger.info(f"Consulta de performance concluída em {duration:.3f}s")
            self.logger.info(f"Resposta: {result.data.get('response', 'N/A')[:100]}...")
            
        except HandoffError as e:
            self.logger.error(f"Erro na consulta de performance: {e}")
    
    async def demo_escalation(self):
        """Demonstra escalação de problemas."""
        self.logger.info("\n=== DEMONSTRAÇÃO: ESCALAÇÃO ===")
        
        # Cenário 1: Escalação de urgência alta
        issue = "Falha crítica no sistema de navegação detectada"
        context = {
            "error_code": "NAV_001",
            "severity": "critical",
            "aircraft": "B737",
            "icao": "SBGR"
        }
        
        start_time = time.time()
        try:
            result = await self.handoff_manager.escalate(
                "weather", "technical", issue, context, UrgencyLevel.CRITICAL
            )
            duration = time.time() - start_time
            
            self.logger.info(f"Escalação crítica concluída em {duration:.3f}s")
            self.logger.info(f"Resposta: {result.data.get('response', 'N/A')[:100]}...")
            
        except HandoffError as e:
            self.logger.error(f"Erro na escalação: {e}")
        
        # Cenário 2: Escalação de urgência média
        issue2 = "Dúvida sobre regulamentação específica"
        context2 = {
            "regulation": "RBAC 121",
            "section": "3.2.1",
            "question": "Aplicabilidade em operações noturnas"
        }
        
        start_time = time.time()
        try:
            result = await self.handoff_manager.escalate(
                "regulatory", "education", issue2, context2, UrgencyLevel.MEDIUM
            )
            duration = time.time() - start_time
            
            self.logger.info(f"Escalação média concluída em {duration:.3f}s")
            self.logger.info(f"Resposta: {result.data.get('response', 'N/A')[:100]}...")
            
        except HandoffError as e:
            self.logger.error(f"Erro na escalação média: {e}")
    
    async def demo_collaboration(self):
        """Demonstra colaboração entre múltiplos agentes."""
        self.logger.info("\n=== DEMONSTRAÇÃO: COLABORAÇÃO ===")
        
        # Cenário 1: Colaboração para análise completa
        agents = ["weather", "regulatory", "performance", "geographic"]
        task = "Análise completa de operação de pouso em SBGR"
        context = {
            "icao": "SBGR",
            "aircraft": "B737",
            "runway": "09L",
            "operation": "landing",
            "detailed_analysis": True
        }
        
        start_time = time.time()
        try:
            result = await self.handoff_manager.collaborate(agents, task, context)
            duration = time.time() - start_time
            
            self.logger.info(f"Colaboração concluída em {duration:.3f}s")
            self.logger.info(f"Agentes participantes: {len(result.data)}")
            
            for agent_id, agent_result in result.data.items():
                if isinstance(agent_result, dict) and "response" in agent_result:
                    self.logger.info(f"  {agent_id}: {agent_result['response'][:50]}...")
                else:
                    self.logger.info(f"  {agent_id}: Resultado processado")
            
        except HandoffError as e:
            self.logger.error(f"Erro na colaboração: {e}")
        
        # Cenário 2: Colaboração para emergência
        agents2 = ["weather", "operations", "communication"]
        task2 = "Planejamento de emergência para SBSP"
        context2 = {
            "icao": "SBSP",
            "emergency_type": "medical",
            "priority": "high"
        }
        
        start_time = time.time()
        try:
            result = await self.handoff_manager.collaborate(agents2, task2, context2)
            duration = time.time() - start_time
            
            self.logger.info(f"Colaboração de emergência concluída em {duration:.3f}s")
            self.logger.info(f"Agentes participantes: {len(result.data)}")
            
        except HandoffError as e:
            self.logger.error(f"Erro na colaboração de emergência: {e}")
    
    async def demo_validation(self):
        """Demonstra validação de dados."""
        self.logger.info("\n=== DEMONSTRAÇÃO: VALIDAÇÃO ===")
        
        # Cenário 1: Validação de dados de voo
        data = {
            "icao": "SBGR",
            "aircraft": "B737",
            "runway": "09L",
            "wind_speed": 15,
            "visibility": 8000
        }
        validation_rules = {
            "icao_required": True,
            "aircraft_valid": True,
            "runway_exists": True,
            "wind_speed_limit": 30,
            "visibility_minimum": 5000
        }
        
        start_time = time.time()
        try:
            result = await self.handoff_manager.validate("regulatory", data, validation_rules)
            duration = time.time() - start_time
            
            self.logger.info(f"Validação concluída em {duration:.3f}s")
            self.logger.info(f"Resultado: {result.data.get('validation_result', 'N/A')}")
            
        except HandoffError as e:
            self.logger.error(f"Erro na validação: {e}")
        
        # Cenário 2: Validação com dados inválidos
        invalid_data = {
            "icao": "INVALID",
            "aircraft": "B999",
            "wind_speed": 50,
            "visibility": 2000
        }
        
        start_time = time.time()
        try:
            result = await self.handoff_manager.validate("regulatory", invalid_data, validation_rules)
            duration = time.time() - start_time
            
            self.logger.info(f"Validação de dados inválidos concluída em {duration:.3f}s")
            self.logger.info(f"Resultado: {result.data.get('validation_result', 'N/A')}")
            
        except HandoffError as e:
            self.logger.error(f"Erro na validação de dados inválidos: {e}")
    
    async def demo_circuit_breaker(self):
        """Demonstra funcionamento do circuit breaker."""
        self.logger.info("\n=== DEMONSTRAÇÃO: CIRCUIT BREAKER ===")
        
        # Simula falhas para abrir o circuit breaker
        self.logger.info("Simulando falhas para testar circuit breaker...")
        
        for i in range(7):
            try:
                # Tenta delegação que vai falhar
                await self.handoff_manager.delegate("test", "inexistent", {"test": "data"})
            except HandoffError as e:
                self.logger.info(f"Falha {i+1}: {e}")
        
        # Verifica estado do circuit breaker
        metrics = self.handoff_manager.get_metrics()
        circuit_state = metrics.get("circuit_breaker", {}).get("state", "UNKNOWN")
        failure_count = metrics.get("circuit_breaker", {}).get("failure_count", 0)
        
        self.logger.info(f"Estado do circuit breaker: {circuit_state}")
        self.logger.info(f"Contagem de falhas: {failure_count}")
        
        # Tenta nova operação (deve ser bloqueada)
        try:
            await self.handoff_manager.delegate("test", "weather", {"test": "data"})
        except HandoffError as e:
            self.logger.info(f"Operação bloqueada pelo circuit breaker: {e}")
        
        # Reseta o circuit breaker
        self.handoff_manager.circuit_breaker.reset()
        self.logger.info("Circuit breaker resetado")
        
        # Verifica se voltou a funcionar
        try:
            result = await self.handoff_manager.delegate("test", "weather", {"test": "data"})
            self.logger.info("Circuit breaker funcionando novamente após reset")
        except HandoffError as e:
            self.logger.error(f"Erro após reset: {e}")
    
    async def demo_metrics(self):
        """Demonstra métricas do sistema."""
        self.logger.info("\n=== DEMONSTRAÇÃO: MÉTRICAS ===")
        
        # Executa algumas operações para gerar métricas
        self.logger.info("Executando operações para gerar métricas...")
        
        # Delegações
        for i in range(3):
            try:
                await self.handoff_manager.delegate("test", "weather", {"test": f"data_{i}"})
            except HandoffError:
                pass
        
        # Consultas
        for i in range(2):
            try:
                await self.handoff_manager.consult("test", "regulatory", f"query_{i}", {"test": "data"})
            except HandoffError:
                pass
        
        # Validações
        for i in range(2):
            try:
                await self.handoff_manager.validate("regulatory", {"test": f"data_{i}"}, {"test": True})
            except HandoffError:
                pass
        
        # Obtém métricas
        metrics = self.handoff_manager.get_metrics()
        
        self.logger.info("Métricas do sistema:")
        for handoff_type, data in metrics.items():
            if isinstance(data, dict) and "total" in data:
                total = data.get("total", 0)
                success = data.get("success", 0)
                failure = data.get("failure", 0)
                avg_duration = data.get("avg_duration", 0.0)
                
                if total > 0:
                    success_rate = (success / total) * 100
                    self.logger.info(f"  {handoff_type}:")
                    self.logger.info(f"    Total: {total}")
                    self.logger.info(f"    Sucesso: {success} ({success_rate:.1f}%)")
                    self.logger.info(f"    Falhas: {failure}")
                    self.logger.info(f"    Duração média: {avg_duration:.3f}s")
        
        # Métricas do circuit breaker
        circuit_data = metrics.get("circuit_breaker", {})
        self.logger.info(f"  Circuit Breaker:")
        self.logger.info(f"    Estado: {circuit_data.get('state', 'UNKNOWN')}")
        self.logger.info(f"    Falhas: {circuit_data.get('failure_count', 0)}")
        
        # Métricas de MCPs
        self.logger.info(f"  MCPs registrados: {metrics.get('registered_mcps', 0)}")
    
    async def demo_complex_scenario(self):
        """Demonstra cenário complexo de handoffs."""
        self.logger.info("\n=== DEMONSTRAÇÃO: CENÁRIO COMPLEXO ===")
        
        # Simula um cenário real de aviação
        scenario = {
            "message": "Piloto reporta problema técnico durante aproximação para SBGR",
            "icao": "SBGR",
            "aircraft": "B737",
            "issue": "Sistema de navegação apresentando anomalias",
            "urgency": "high",
            "phase": "approach"
        }
        
        self.logger.info("Iniciando cenário complexo...")
        start_time = time.time()
        
        try:
            # 1. Delegação para agente técnico
            self.logger.info("1. Delegando para agente técnico...")
            tech_result = await self.handoff_manager.delegate(
                "orchestrator", "technical", scenario
            )
            
            # 2. Consulta com agente meteorológico
            self.logger.info("2. Consultando condições meteorológicas...")
            weather_query = "Condições meteorológicas atuais em SBGR"
            weather_result = await self.handoff_manager.consult(
                "technical", "weather", weather_query, {"icao": "SBGR"}
            )
            
            # 3. Escalação para operações
            self.logger.info("3. Escalando para operações...")
            escalation_issue = "Problema técnico requer coordenação operacional"
            ops_result = await self.handoff_manager.escalate(
                "technical", "operations", escalation_issue, scenario, UrgencyLevel.HIGH
            )
            
            # 4. Colaboração entre múltiplos agentes
            self.logger.info("4. Iniciando colaboração entre agentes...")
            collaboration_agents = ["technical", "weather", "operations", "communication"]
            collaboration_task = "Análise completa e plano de ação"
            collab_result = await self.handoff_manager.collaborate(
                collaboration_agents, collaboration_task, scenario
            )
            
            # 5. Validação final
            self.logger.info("5. Validando plano de ação...")
            validation_data = {
                "plan": "Pouso de emergência em SBGR",
                "runway": "09L",
                "priority": "high"
            }
            validation_rules = {
                "plan_valid": True,
                "runway_available": True,
                "priority_appropriate": True
            }
            validation_result = await self.handoff_manager.validate(
                "operations", validation_data, validation_rules
            )
            
            total_duration = time.time() - start_time
            self.logger.info(f"Cenário complexo concluído em {total_duration:.3f}s")
            
            # Resumo dos resultados
            self.logger.info("Resumo dos resultados:")
            self.logger.info(f"  Técnico: {tech_result.success}")
            self.logger.info(f"  Meteorologia: {weather_result.success}")
            self.logger.info(f"  Operações: {ops_result.success}")
            self.logger.info(f"  Colaboração: {collab_result.success}")
            self.logger.info(f"  Validação: {validation_result.success}")
            
        except HandoffError as e:
            total_duration = time.time() - start_time
            self.logger.error(f"Erro no cenário complexo após {total_duration:.3f}s: {e}")
    
    async def run_all_demos(self):
        """Executa todas as demonstrações."""
        self.logger.info("🚀 INICIANDO DEMONSTRAÇÃO DO SISTEMA DE HANDOFFS")
        self.logger.info("=" * 60)
        
        try:
            await self.demo_delegation()
            await self.demo_consultation()
            await self.demo_escalation()
            await self.demo_collaboration()
            await self.demo_validation()
            await self.demo_circuit_breaker()
            await self.demo_metrics()
            await self.demo_complex_scenario()
            
            self.logger.info("\n" + "=" * 60)
            self.logger.info("✅ DEMONSTRAÇÃO CONCLUÍDA COM SUCESSO")
            
        except Exception as e:
            self.logger.error(f"❌ Erro durante demonstração: {e}")
            raise


async def main():
    """Função principal."""
    demo = HandoffDemo()
    await demo.run_all_demos()


if __name__ == "__main__":
    asyncio.run(main()) 