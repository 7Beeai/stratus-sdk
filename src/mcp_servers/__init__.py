"""
MCP Servers do Stratus.IA - Sistema de IA para Aviação Civil Brasileira
Exporta todos os servidores MCP e suas ferramentas para uso em agentes e API
"""

# Importar todos os MCPs servers existentes
from .aisweb_server import AISWEBMCPServer, MCP_TOOLS as AISWEB_MCP_TOOLS
from .pinecone_server import PineconeMCPServer, MCP_TOOLS as PINECONE_MCP_TOOLS
from .redemet_server import RedemetMCPServer, MCP_TOOLS as REDEMET_MCP_TOOLS
from .additional_servers import (
    AirportDBMCPServer, RapidAPIDistanceMCPServer, AviationWeatherGovMCPServer,
    TomorrowIOMCPServer, ANACRegulationsMCPServer, ADDITIONAL_MCP_TOOLS
)
from src.agents.handoffs import handoff_manager, MCPEnum

# Combinar todos os MCP tools em um dicionário unificado
ALL_MCP_TOOLS = {
    # AISWEB Tools (14 tools)
    **AISWEB_MCP_TOOLS,
    
    # Pinecone Tools (4 tools)
    **PINECONE_MCP_TOOLS,
    
    # REDEMET Tools (6 tools)
    **REDEMET_MCP_TOOLS,
    
    # Additional Tools (15 tools)
    **ADDITIONAL_MCP_TOOLS
}

# Lista de todos os servidores MCP
ALL_MCP_SERVERS = {
    'aisweb': AISWEBMCPServer,
    'pinecone': PineconeMCPServer,
    'redemet': RedemetMCPServer,
    'airportdb': AirportDBMCPServer,
    'distance': RapidAPIDistanceMCPServer,
    'aviation_weather': AviationWeatherGovMCPServer,
    'tomorrow_io': TomorrowIOMCPServer,
    'anac_regulations': ANACRegulationsMCPServer
}

# Estatísticas dos MCPs
MCP_STATISTICS = {
    'total_servers': 8,
    'total_tools': 39,  # 14 + 4 + 6 + 15
    'servers_by_category': {
        'aviation_data': ['aisweb', 'redemet', 'aviation_weather'],
        'weather': ['redemet', 'aviation_weather', 'tomorrow_io'],
        'airports': ['airportdb'],
        'navigation': ['distance'],
        'regulations': ['anac_regulations'],
        'vector_search': ['pinecone']
    }
}

# Configurações de cache por servidor
CACHE_CONFIGURATIONS = {
    'aisweb': {
        'default_ttl': 3600,  # 1 hora
        'notam_ttl': 300,     # 5 minutos (crítico)
        'metar_ttl': 600      # 10 minutos
    },
    'pinecone': {
        'default_ttl': 1800,  # 30 minutos
        'search_ttl': 300     # 5 minutos
    },
    'redemet': {
        'default_ttl': 1800,  # 30 minutos
        'metar_ttl': 600,     # 10 minutos
        'taf_ttl': 1800       # 30 minutos
    },
    'airportdb': {
        'default_ttl': 86400  # 24 horas (dados estáticos)
    },
    'distance': {
        'default_ttl': 43200  # 12 horas (semi-estático)
    },
    'aviation_weather': {
        'metar_ttl': 1800,    # 30 minutos
        'taf_ttl': 3600,      # 1 hora
        'pirep_ttl': 1800,    # 30 minutos
        'isigmet_ttl': 600,   # 10 minutos (crítico)
        'windtemp_ttl': 3600  # 1 hora
    },
    'tomorrow_io': {
        'realtime_ttl': 900,   # 15 minutos
        'forecast_ttl': 3600,  # 1 hora
        'history_ttl': 86400,  # 24 horas
        'timelines_ttl': 3600, # 1 hora
        'maps_ttl': 1800       # 30 minutos
    },
    'anac_regulations': {
        'default_ttl': 86400   # 24 horas (regulamentações)
    }
}

# Configurações de circuit breaker por servidor
CIRCUIT_BREAKER_CONFIGURATIONS = {
    'aisweb': {'failure_threshold': 3, 'timeout_duration': 15},
    'pinecone': {'failure_threshold': 3, 'timeout_duration': 10},
    'redemet': {'failure_threshold': 3, 'timeout_duration': 15},
    'airportdb': {'failure_threshold': 3, 'timeout_duration': 15},
    'distance': {'failure_threshold': 3, 'timeout_duration': 15},
    'aviation_weather': {'failure_threshold': 3, 'timeout_duration': 15},
    'tomorrow_io': {'failure_threshold': 3, 'timeout_duration': 15},
    'anac_regulations': {'failure_threshold': 3, 'timeout_duration': 30}
}

def get_mcp_server(server_name: str):
    """Obtém uma instância de servidor MCP pelo nome"""
    if server_name not in ALL_MCP_SERVERS:
        raise ValueError(f"Servidor MCP não encontrado: {server_name}")
    return ALL_MCP_SERVERS[server_name]

def get_mcp_tool(tool_name: str):
    """Obtém uma ferramenta MCP pelo nome"""
    if tool_name not in ALL_MCP_TOOLS:
        raise ValueError(f"Ferramenta MCP não encontrada: {tool_name}")
    return ALL_MCP_TOOLS[tool_name]

def list_available_servers():
    """Lista todos os servidores MCP disponíveis"""
    return list(ALL_MCP_SERVERS.keys())

def list_available_tools():
    """Lista todas as ferramentas MCP disponíveis"""
    return list(ALL_MCP_TOOLS.keys())

def get_tools_by_category(category: str):
    """Obtém ferramentas por categoria"""
    if category not in MCP_STATISTICS['servers_by_category']:
        return []
    
    tools = []
    for server in MCP_STATISTICS['servers_by_category'][category]:
        if server == 'aisweb':
            tools.extend(AISWEB_MCP_TOOLS.keys())
        elif server == 'pinecone':
            tools.extend(PINECONE_MCP_TOOLS.keys())
        elif server == 'redemet':
            tools.extend(REDEMET_MCP_TOOLS.keys())
        elif server in ['airportdb', 'distance', 'aviation_weather', 'tomorrow_io', 'anac_regulations']:
            # Filtrar tools do servidor específico
            for tool_name, tool_func in ADDITIONAL_MCP_TOOLS.items():
                if tool_name.startswith(server.replace('_', '')):
                    tools.append(tool_name)
    
    return tools

# Registra MCPs no HandoffManager
handoff_manager.register_mcp(MCPEnum.REDEMET, RedemetMCPServer)
handoff_manager.register_mcp(MCPEnum.AISWEB, AISWEBMCPServer)
handoff_manager.register_mcp(MCPEnum.PINECONE, PineconeMCPServer)
handoff_manager.register_mcp(MCPEnum.AIRPORTDB, AirportDBMCPServer)
handoff_manager.register_mcp(MCPEnum.WEATHER_APIS, AviationWeatherGovMCPServer)
handoff_manager.register_mcp(MCPEnum.ANAC_REGULATIONS, ANACRegulationsMCPServer)
# Adicione outros MCPs conforme necessário

# Exportar tudo
__all__ = [
    # Servidores
    'AISWEBMCPServer', 'PineconeMCPServer', 'RedemetMCPServer',
    'AirportDBMCPServer', 'RapidAPIDistanceMCPServer', 'AviationWeatherGovMCPServer',
    'TomorrowIOMCPServer', 'ANACRegulationsMCPServer',
    
    # Tools
    'AISWEB_MCP_TOOLS', 'PINECONE_MCP_TOOLS', 'REDEMET_MCP_TOOLS', 'ADDITIONAL_MCP_TOOLS',
    'ALL_MCP_TOOLS',
    
    # Configurações
    'ALL_MCP_SERVERS', 'MCP_STATISTICS', 'CACHE_CONFIGURATIONS', 'CIRCUIT_BREAKER_CONFIGURATIONS',
    
    # Funções utilitárias
    'get_mcp_server', 'get_mcp_tool', 'list_available_servers', 'list_available_tools', 'get_tools_by_category',
    'redemet_server',
    'aisweb_server', 
    'pinecone_server',
    'airportdb_server',
    'weather_apis_server',
    'anac_regulations_server'
] 