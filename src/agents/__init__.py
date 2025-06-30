"""
Stratus.IA Agents Module

Este módulo contém os agentes especializados do sistema Stratus.IA:
- Router Agent: Classificador inteligente de mensagens
- Orchestrator Agent: Coordenador central de agentes especialistas

Baseado no prompt original do Stratus.IA, adaptado para arquitetura de agentes especializados.
"""

from .router import (
    StratusRouterAgent,
    MessageCategory,
    UrgencyLevel,
    MessageClassification,
    ExtractedEntities,
    router_agent
)

from .orchestrator import (
    StratusOrchestratorAgent,
    AgentResponse,
    SynthesizedResponse,
    orchestrator_agent
)

__all__ = [
    # Router Agent
    'StratusRouterAgent',
    'MessageCategory', 
    'UrgencyLevel',
    'MessageClassification',
    'ExtractedEntities',
    'router_agent',
    
    # Orchestrator Agent
    'StratusOrchestratorAgent',
    'AgentResponse',
    'SynthesizedResponse',
    'orchestrator_agent'
]

# Versão do módulo
__version__ = "1.0.0"

# Informações do módulo
__author__ = "Stratus.IA Team"
__description__ = "Agentes especializados para aviação civil brasileira"
__license__ = "Proprietary" 