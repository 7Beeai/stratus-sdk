"""
Testes para o sistema de handoffs entre agentes.
Testa delegação, consulta, escalação, colaboração, validação e MCPs.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from src.agents.handoffs import (
    HandoffManager, HandoffType, UrgencyLevel, MCPEnum,
    HandoffResult, HandoffError, CircuitBreaker, HandoffMetrics
)


class MockAgent:
    """Agente mock para testes."""
    
    def __init__(self, agent_id: str, should_fail: bool = False, delay: float = 0.1):
        self.agent_id = agent_id
        self.should_fail = should_fail
        self.delay = delay
        self.calls = []
    
    async def process_with_handoffs(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Processa com handoffs."""
        self.calls.append(("process_with_handoffs", context))
        await asyncio.sleep(self.delay)
        
        if self.should_fail:
            raise Exception(f"Erro simulado em {self.agent_id}")
        
        return {
            "agent_id": self.agent_id,
            "result": f"Processado por {self.agent_id}",
            "context": context
        }
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Processa normalmente."""
        self.calls.append(("process", context))
        await asyncio.sleep(self.delay)
        
        if self.should_fail:
            raise Exception(f"Erro simulado em {self.agent_id}")
        
        return {
            "agent_id": self.agent_id,
            "result": f"Processado por {self.agent_id}",
            "context": context
        }
    
    async def consult(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Consulta."""
        self.calls.append(("consult", query, context))
        await asyncio.sleep(self.delay)
        
        if self.should_fail:
            raise Exception(f"Erro simulado em {self.agent_id}")
        
        return {
            "agent_id": self.agent_id,
            "query": query,
            "response": f"Resposta de {self.agent_id}",
            "context": context
        }
    
    async def handle_escalation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Trata escalação."""
        self.calls.append(("handle_escalation", context))
        await asyncio.sleep(self.delay)
        
        if self.should_fail:
            raise Exception(f"Erro simulado em {self.agent_id}")
        
        return {
            "agent_id": self.agent_id,
            "escalation_handled": True,
            "issue": context.get("issue"),
            "urgency": context.get("urgency")
        }
    
    async def collaborate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Colabora."""
        self.calls.append(("collaborate", context))
        await asyncio.sleep(self.delay)
        
        if self.should_fail:
            raise Exception(f"Erro simulado em {self.agent_id}")
        
        return {
            "agent_id": self.agent_id,
            "collaboration_result": f"Colaboração de {self.agent_id}",
            "task": context.get("task")
        }
    
    async def validate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Valida."""
        self.calls.append(("validate", context))
        await asyncio.sleep(self.delay)
        
        if self.should_fail:
            raise Exception(f"Erro simulado em {self.agent_id}")
        
        return {
            "agent_id": self.agent_id,
            "validation_result": True,
            "data": context.get("data"),
            "rules": context.get("validation_rules")
        }


class MockMCPServer:
    """MCP Server mock para testes."""
    
    def __init__(self, mcp_type: MCPEnum, should_fail: bool = False):
        self.mcp_type = mcp_type
        self.should_fail = should_fail
        self.calls = []
    
    async def get_weather_data(self, icao: str) -> Dict[str, Any]:
        """Simula obtenção de dados meteorológicos."""
        self.calls.append(("get_weather_data", icao))
        
        if self.should_fail:
            raise Exception(f"Erro simulado no MCP {self.mcp_type.value}")
        
        return {
            "icao": icao,
            "temperature": 25.0,
            "wind_speed": 10.0,
            "visibility": 10000
        }


@pytest.fixture
def handoff_manager():
    """Fixture para HandoffManager."""
    return HandoffManager()


@pytest.fixture
def mock_agents():
    """Fixture para agentes mock."""
    return {
        "weather": MockAgent("weather"),
        "regulatory": MockAgent("regulatory"),
        "performance": MockAgent("performance"),
        "technical": MockAgent("technical"),
        "failing_agent": MockAgent("failing_agent", should_fail=True),
        "slow_agent": MockAgent("slow_agent", delay=2.0)
    }


@pytest.fixture
def mock_mcps():
    """Fixture para MCPs mock."""
    return {
        MCPEnum.REDEMET: MockMCPServer(MCPEnum.REDEMET),
        MCPEnum.AISWEB: MockMCPServer(MCPEnum.AISWEB),
        MCPEnum.PINECONE: MockMCPServer(MCPEnum.PINECONE),
        MCPEnum.WEATHER_APIS: MockMCPServer(MCPEnum.WEATHER_APIS, should_fail=True)
    }


class TestHandoffManager:
    """Testes para HandoffManager."""
    
    def test_initialization(self, handoff_manager):
        """Testa inicialização do HandoffManager."""
        assert handoff_manager.agents == {}
        assert handoff_manager.mcps == {}
        assert handoff_manager.circuit_breaker is not None
        assert handoff_manager.metrics is not None
    
    def test_register_agent(self, handoff_manager, mock_agents):
        """Testa registro de agentes."""
        agent = mock_agents["weather"]
        handoff_manager.register_agent("weather", agent)
        
        assert "weather" in handoff_manager.agents
        assert handoff_manager.agents["weather"] == agent
    
    def test_register_mcp(self, handoff_manager, mock_mcps):
        """Testa registro de MCPs."""
        mcp = mock_mcps[MCPEnum.REDEMET]
        handoff_manager.register_mcp(MCPEnum.REDEMET, mcp)
        
        assert MCPEnum.REDEMET in handoff_manager.mcps
        assert handoff_manager.mcps[MCPEnum.REDEMET] == mcp
    
    @pytest.mark.asyncio
    async def test_delegate_success(self, handoff_manager, mock_agents):
        """Testa delegação bem-sucedida."""
        agent = mock_agents["weather"]
        handoff_manager.register_agent("weather", agent)
        
        context = {"message": "test", "icao": "SBGR"}
        result = await handoff_manager.delegate("orchestrator", "weather", context)
        
        assert result.success is True
        assert result.handoff_type == HandoffType.DELEGATION
        assert result.data["agent_id"] == "weather"
        assert len(agent.calls) == 1
        assert agent.calls[0][0] == "process_with_handoffs"
    
    @pytest.mark.asyncio
    async def test_delegate_agent_not_found(self, handoff_manager):
        """Testa delegação para agente inexistente."""
        context = {"message": "test"}
        
        with pytest.raises(HandoffError, match="Agente não encontrado"):
            await handoff_manager.delegate("orchestrator", "inexistent", context)
    
    @pytest.mark.asyncio
    async def test_delegate_timeout(self, handoff_manager, mock_agents):
        """Testa timeout na delegação."""
        agent = mock_agents["slow_agent"]
        handoff_manager.register_agent("slow", agent)
        
        context = {"message": "test"}
        
        with pytest.raises(HandoffError, match="Timeout na delegação"):
            await handoff_manager.delegate("orchestrator", "slow", context, timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_delegate_agent_error(self, handoff_manager, mock_agents):
        """Testa erro no agente durante delegação."""
        agent = mock_agents["failing_agent"]
        handoff_manager.register_agent("failing", agent)
        
        context = {"message": "test"}
        
        with pytest.raises(HandoffError, match="Erro na delegação"):
            await handoff_manager.delegate("orchestrator", "failing", context)
    
    @pytest.mark.asyncio
    async def test_consult_success(self, handoff_manager, mock_agents):
        """Testa consulta bem-sucedida."""
        agent = mock_agents["regulatory"]
        handoff_manager.register_agent("regulatory", agent)
        
        query = "Qual a regulamentação para pouso em SBGR?"
        context = {"icao": "SBGR"}
        result = await handoff_manager.consult("orchestrator", "regulatory", query, context)
        
        assert result.success is True
        assert result.handoff_type == HandoffType.CONSULTATION
        assert result.data["agent_id"] == "regulatory"
        assert result.data["query"] == query
        assert len(agent.calls) == 1
        assert agent.calls[0][0] == "consult"
    
    @pytest.mark.asyncio
    async def test_consult_timeout(self, handoff_manager, mock_agents):
        """Testa timeout na consulta."""
        agent = mock_agents["slow_agent"]
        handoff_manager.register_agent("slow", agent)
        
        query = "test"
        context = {"test": "data"}
        
        with pytest.raises(HandoffError, match="Timeout na consulta"):
            await handoff_manager.consult("orchestrator", "slow", query, context, timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_escalate_success(self, handoff_manager, mock_agents):
        """Testa escalação bem-sucedida."""
        agent = mock_agents["technical"]
        handoff_manager.register_agent("technical", agent)
        
        issue = "Problema crítico no sistema"
        context = {"error_code": "E001"}
        result = await handoff_manager.escalate("weather", "technical", issue, context, UrgencyLevel.CRITICAL)
        
        assert result.success is True
        assert result.handoff_type == HandoffType.ESCALATION
        assert result.data["agent_id"] == "technical"
        assert result.data["issue"] == issue
        assert result.data["urgency"] == UrgencyLevel.CRITICAL.value
        assert len(agent.calls) == 1
        assert agent.calls[0][0] == "handle_escalation"
    
    @pytest.mark.asyncio
    async def test_collaborate_success(self, handoff_manager, mock_agents):
        """Testa colaboração bem-sucedida."""
        agents = ["weather", "regulatory", "performance"]
        for agent_id in agents:
            handoff_manager.register_agent(agent_id, mock_agents[agent_id])
        
        task = "Análise completa de operação"
        context = {"operation": "test"}
        result = await handoff_manager.collaborate(agents, task, context)
        
        assert result.success is True
        assert result.handoff_type == HandoffType.COLLABORATION
        assert len(result.data) == 3
        
        for agent_id in agents:
            assert agent_id in result.data
            assert result.data[agent_id]["agent_id"] == agent_id
    
    @pytest.mark.asyncio
    async def test_validate_success(self, handoff_manager, mock_agents):
        """Testa validação bem-sucedida."""
        agent = mock_agents["regulatory"]
        handoff_manager.register_agent("regulatory", agent)
        
        data = {"icao": "SBGR", "operation": "landing"}
        validation_rules = {"icao_required": True, "operation_valid": True}
        result = await handoff_manager.validate("regulatory", data, validation_rules)
        
        assert result.success is True
        assert result.handoff_type == HandoffType.VALIDATION
        assert result.data["agent_id"] == "regulatory"
        assert result.data["validation_result"] is True
        assert len(agent.calls) == 1
        assert agent.calls[0][0] == "validate"


class TestCircuitBreaker:
    """Testes para CircuitBreaker."""
    
    def test_initial_state(self):
        """Testa estado inicial do circuit breaker."""
        cb = CircuitBreaker()
        assert cb.state.value == "CLOSED"
        assert cb.failure_count == 0
        assert cb.last_failure is None
    
    def test_can_execute_closed(self):
        """Testa execução com circuit breaker fechado."""
        cb = CircuitBreaker()
        assert cb.can_execute() is True
    
    def test_can_execute_open(self):
        """Testa execução com circuit breaker aberto."""
        cb = CircuitBreaker()
        cb.state = cb.State.OPEN
        assert cb.can_execute() is False
    
    def test_record_success(self):
        """Testa registro de sucesso."""
        cb = CircuitBreaker()
        cb.failure_count = 5
        cb.record_success()
        
        assert cb.failure_count == 0
        assert cb.state.value == "CLOSED"
    
    def test_record_failure(self):
        """Testa registro de falha."""
        cb = CircuitBreaker()
        
        # Primeiras falhas
        for i in range(5):
            cb.record_failure()
            assert cb.failure_count == i + 1
            assert cb.state.value == "CLOSED"
        
        # Falha que abre o circuit breaker
        cb.record_failure()
        assert cb.failure_count == 6
        assert cb.state.value == "OPEN"
        assert cb.last_failure is not None
    
    def test_half_open_transition(self):
        """Testa transição para half-open."""
        cb = CircuitBreaker()
        cb.state = cb.State.OPEN
        cb.last_failure = datetime.now() - timedelta(seconds=61)  # Mais de 1 minuto
        
        assert cb.can_execute() is True
        assert cb.state.value == "HALF_OPEN"
    
    def test_reset(self):
        """Testa reset do circuit breaker."""
        cb = CircuitBreaker()
        cb.failure_count = 10
        cb.state = cb.State.OPEN
        cb.last_failure = datetime.now()
        
        cb.reset()
        
        assert cb.failure_count == 0
        assert cb.state.value == "CLOSED"
        assert cb.last_failure is None


class TestHandoffMetrics:
    """Testes para HandoffMetrics."""
    
    def test_initial_state(self):
        """Testa estado inicial das métricas."""
        metrics = HandoffMetrics()
        
        for handoff_type in HandoffType:
            assert metrics.metrics[handoff_type.value]["total"] == 0
            assert metrics.metrics[handoff_type.value]["success"] == 0
            assert metrics.metrics[handoff_type.value]["failure"] == 0
            assert metrics.metrics[handoff_type.value]["total_duration"] == 0.0
            assert metrics.metrics[handoff_type.value]["avg_duration"] == 0.0
    
    def test_record_delegation(self):
        """Testa registro de delegação."""
        metrics = HandoffMetrics()
        
        # Sucesso
        metrics.record_delegation(1.5, True)
        assert metrics.metrics["delegation"]["total"] == 1
        assert metrics.metrics["delegation"]["success"] == 1
        assert metrics.metrics["delegation"]["failure"] == 0
        assert metrics.metrics["delegation"]["total_duration"] == 1.5
        assert metrics.metrics["delegation"]["avg_duration"] == 1.5
        
        # Falha
        metrics.record_delegation(0.5, False)
        assert metrics.metrics["delegation"]["total"] == 2
        assert metrics.metrics["delegation"]["success"] == 1
        assert metrics.metrics["delegation"]["failure"] == 1
        assert metrics.metrics["delegation"]["total_duration"] == 2.0
        assert metrics.metrics["delegation"]["avg_duration"] == 1.0
    
    def test_record_consultation(self):
        """Testa registro de consulta."""
        metrics = HandoffMetrics()
        
        metrics.record_consultation(0.8, True)
        assert metrics.metrics["consultation"]["total"] == 1
        assert metrics.metrics["consultation"]["success"] == 1
        assert metrics.metrics["consultation"]["avg_duration"] == 0.8
    
    def test_record_escalation(self):
        """Testa registro de escalação."""
        metrics = HandoffMetrics()
        
        metrics.record_escalation(2.0, True)
        assert metrics.metrics["escalation"]["total"] == 1
        assert metrics.metrics["escalation"]["success"] == 1
        assert metrics.metrics["escalation"]["avg_duration"] == 2.0
    
    def test_record_collaboration(self):
        """Testa registro de colaboração."""
        metrics = HandoffMetrics()
        
        metrics.record_collaboration(3.5, True)
        assert metrics.metrics["collaboration"]["total"] == 1
        assert metrics.metrics["collaboration"]["success"] == 1
        assert metrics.metrics["collaboration"]["avg_duration"] == 3.5
    
    def test_record_validation(self):
        """Testa registro de validação."""
        metrics = HandoffMetrics()
        
        metrics.record_validation(0.3, True)
        assert metrics.metrics["validation"]["total"] == 1
        assert metrics.metrics["validation"]["success"] == 1
        assert metrics.metrics["validation"]["avg_duration"] == 0.3
    
    def test_get_summary(self):
        """Testa obtenção de resumo das métricas."""
        metrics = HandoffMetrics()
        
        # Adiciona alguns dados
        metrics.record_delegation(1.0, True)
        metrics.record_delegation(2.0, False)
        metrics.record_consultation(0.5, True)
        
        summary = metrics.get_summary()
        
        assert "delegation" in summary
        assert "consultation" in summary
        assert summary["delegation"]["total"] == 2
        assert summary["delegation"]["success_rate"] == 0.5
        assert summary["consultation"]["total"] == 1
        assert summary["consultation"]["success_rate"] == 1.0
    
    def test_reset(self):
        """Testa reset das métricas."""
        metrics = HandoffMetrics()
        
        # Adiciona dados
        metrics.record_delegation(1.0, True)
        metrics.record_consultation(0.5, True)
        
        # Reseta
        metrics.reset()
        
        # Verifica se foi resetado
        for handoff_type in HandoffType:
            assert metrics.metrics[handoff_type.value]["total"] == 0
            assert metrics.metrics[handoff_type.value]["success"] == 0
            assert metrics.metrics[handoff_type.value]["failure"] == 0


class TestHandoffIntegration:
    """Testes de integração do sistema de handoffs."""
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self, handoff_manager, mock_agents):
        """Testa workflow completo de handoffs."""
        # Registra agentes
        for agent_id, agent in mock_agents.items():
            if agent_id != "failing_agent":
                handoff_manager.register_agent(agent_id, agent)
        
        # 1. Delegação
        context1 = {"message": "Consulta meteorológica", "icao": "SBGR"}
        result1 = await handoff_manager.delegate("orchestrator", "weather", context1)
        assert result1.success is True
        
        # 2. Consulta
        query = "Regulamentação para pouso"
        context2 = {"icao": "SBGR"}
        result2 = await handoff_manager.consult("weather", "regulatory", query, context2)
        assert result2.success is True
        
        # 3. Validação
        data = {"icao": "SBGR", "operation": "landing"}
        rules = {"icao_required": True}
        result3 = await handoff_manager.validate("regulatory", data, rules)
        assert result3.success is True
        
        # 4. Colaboração
        agents = ["weather", "regulatory", "performance"]
        task = "Análise completa"
        context4 = {"operation": "test"}
        result4 = await handoff_manager.collaborate(agents, task, context4)
        assert result4.success is True
        
        # Verifica métricas
        metrics = handoff_manager.get_metrics()
        assert metrics["delegation"]["total"] == 1
        assert metrics["consultation"]["total"] == 4  # 1 direta + 3 da colaboração
        assert metrics["validation"]["total"] == 1
        assert metrics["collaboration"]["total"] == 1
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, handoff_manager, mock_agents):
        """Testa integração com circuit breaker."""
        # Registra agente que falha
        handoff_manager.register_agent("failing", mock_agents["failing_agent"])
        
        # Primeiras tentativas (circuit breaker fechado)
        for i in range(5):
            with pytest.raises(HandoffError):
                await handoff_manager.delegate("orchestrator", "failing", {"test": "data"})
        
        # Circuit breaker deve estar aberto agora
        with pytest.raises(HandoffError, match="Circuit breaker aberto"):
            await handoff_manager.delegate("orchestrator", "failing", {"test": "data"})
        
        # Verifica estado do circuit breaker
        breaker = handoff_manager.circuit_breakers.get("failing")
        assert breaker.state.value == "OPEN"
        assert breaker.failure_count == 6
    
    @pytest.mark.asyncio
    async def test_mcp_integration(self, handoff_manager, mock_mcps):
        """Testa integração com MCPs."""
        # Registra MCPs
        for mcp_type, mcp in mock_mcps.items():
            handoff_manager.register_mcp(mcp_type, mcp)
        
        # Verifica se foram registrados
        metrics = handoff_manager.get_metrics()
        assert metrics["registered_mcps"] == 4
        
        # Testa acesso aos MCPs
        assert MCPEnum.REDEMET in handoff_manager.mcps
        assert MCPEnum.AISWEB in handoff_manager.mcps
        assert MCPEnum.PINECONE in handoff_manager.mcps
        assert MCPEnum.WEATHER_APIS in handoff_manager.mcps


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 