#!/usr/bin/env python3
"""
Demonstração dos 5 MCPs Servers Adicionais do Stratus.IA
Testa AirportDB, RapidAPI Distance, Aviation Weather Gov, Tomorrow.io e ANAC Regulations
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any

from src.mcp_servers.additional_servers import (
    AirportDBMCPServer, RapidAPIDistanceMCPServer, AviationWeatherGovMCPServer,
    TomorrowIOMCPServer, ANACRegulationsMCPServer, ADDITIONAL_MCP_TOOLS
)
from src.utils.logging import get_logger

logger = get_logger()

class AdditionalServersDemo:
    """Demonstração completa dos 5 MCPs servers adicionais"""
    
    def __init__(self):
        self.results = {}
        self.start_time = None
        self.end_time = None
    
    async def test_airportdb_server(self):
        """Testa AirportDB MCP Server"""
        print("\n" + "="*60)
        print("🛫 TESTANDO AIRPORTDB MCP SERVER")
        print("="*60)
        
        try:
            async with AirportDBMCPServer() as server:
                # Teste com aeródromos brasileiros
                test_airports = ["SBGR", "SBSP", "SBFL", "SBBR", "SBKP"]
                
                for icao in test_airports:
                    print(f"\n📋 Obtendo dados do aeródromo {icao}...")
                    start = time.time()
                    
                    result = await server.get_airport_info(icao, "demo_user")
                    
                    response_time = (time.time() - start) * 1000
                    print(f"✅ {icao}: {result.airport_data.get('name', 'N/A')}")
                    print(f"   📍 Localização: {result.airport_data.get('latitude', 'N/A')}, {result.airport_data.get('longitude', 'N/A')}")
                    print(f"   🏗️  Tipo: {result.airport_data.get('type', 'N/A')}")
                    print(f"   ⏱️  Tempo: {response_time:.2f}ms | Cache: {result.cached}")
                
                self.results['airportdb'] = {
                    'status': 'success',
                    'airports_tested': len(test_airports),
                    'response_time_avg': response_time
                }
                
        except Exception as e:
            print(f"❌ Erro no AirportDB: {e}")
            self.results['airportdb'] = {'status': 'error', 'error': str(e)}
    
    async def test_distance_server(self):
        """Testa RapidAPI Distance MCP Server"""
        print("\n" + "="*60)
        print("📏 TESTANDO RAPIDAPI DISTANCE MCP SERVER")
        print("="*60)
        
        try:
            async with RapidAPIDistanceMCPServer() as server:
                # Teste com rotas brasileiras
                test_routes = [
                    ["SBGR", "SBSP"],  # São Paulo - Congonhas
                    ["SBGR", "SBBR"],  # São Paulo - Brasília
                    ["SBSP", "SBFL"],  # Congonhas - Florianópolis
                ]
                
                for route in test_routes:
                    print(f"\n🛩️ Calculando distância: {' -> '.join(route)}...")
                    start = time.time()
                    
                    result = await server.calculate_route_distance(route, True, "demo_user")
                    
                    response_time = (time.time() - start) * 1000
                    print(f"✅ Rota: {' -> '.join(route)}")
                    print(f"   📊 Dados: {len(str(result.distance_data))} bytes")
                    print(f"   ⏱️ Tempo: {response_time:.2f}ms | Cache: {result.cached}")
                
                self.results['distance'] = {
                    'status': 'success',
                    'routes_tested': len(test_routes),
                    'response_time_avg': response_time
                }
                
        except Exception as e:
            print(f"❌ Erro no Distance: {e}")
            self.results['distance'] = {'status': 'error', 'error': str(e)}
    
    async def test_aviation_weather_server(self):
        """Testa Aviation Weather Gov MCP Server"""
        print("\n" + "="*60)
        print("🌤️ TESTANDO AVIATION WEATHER GOV MCP SERVER")
        print("="*60)
        
        try:
            async with AviationWeatherGovMCPServer() as server:
                # Teste com estações brasileiras
                test_stations = ["SBGR", "SBSP", "SBBR"]
                
                # Teste METAR
                print(f"\n📡 Obtendo METAR para {', '.join(test_stations)}...")
                start = time.time()
                metar_result = await server.get_metar(test_stations, "json", "demo_user")
                metar_time = (time.time() - start) * 1000
                print(f"✅ METAR: {len(str(metar_result.weather_data))} bytes | {metar_time:.2f}ms | Cache: {metar_result.cached}")
                
                # Teste TAF
                print(f"\n📡 Obtendo TAF para {', '.join(test_stations)}...")
                start = time.time()
                taf_result = await server.get_taf(test_stations, "json", "demo_user")
                taf_time = (time.time() - start) * 1000
                print(f"✅ TAF: {len(str(taf_result.weather_data))} bytes | {taf_time:.2f}ms | Cache: {taf_result.cached}")
                
                # Teste PIREP
                print(f"\n📡 Obtendo PIREP para {', '.join(test_stations)}...")
                start = time.time()
                pirep_result = await server.get_pirep(test_stations, "json", "demo_user")
                pirep_time = (time.time() - start) * 1000
                print(f"✅ PIREP: {len(str(pirep_result.weather_data))} bytes | {pirep_time:.2f}ms | Cache: {pirep_result.cached}")
                
                self.results['aviation_weather'] = {
                    'status': 'success',
                    'endpoints_tested': ['metar', 'taf', 'pirep'],
                    'response_time_avg': (metar_time + taf_time + pirep_time) / 3
                }
                
        except Exception as e:
            print(f"❌ Erro no Aviation Weather: {e}")
            self.results['aviation_weather'] = {'status': 'error', 'error': str(e)}
    
    async def test_tomorrow_io_server(self):
        """Testa Tomorrow.io MCP Server"""
        print("\n" + "="*60)
        print("🌦️ TESTANDO TOMORROW.IO WEATHER MCP SERVER")
        print("="*60)
        
        try:
            async with TomorrowIOMCPServer() as server:
                # Teste com localizações brasileiras
                test_locations = ["SBGR", "-23.5505,-46.6333"]  # São Paulo
                
                for location in test_locations:
                    print(f"\n📍 Testando localização: {location}")
                    
                    # Teste Realtime
                    print(f"   🌡️ Obtendo dados em tempo real...")
                    start = time.time()
                    realtime_result = await server.get_realtime_weather(location, None, "demo_user")
                    realtime_time = (time.time() - start) * 1000
                    print(f"   ✅ Realtime: {len(str(realtime_result.weather_data))} bytes | {realtime_time:.2f}ms | Cache: {realtime_result.cached}")
                    
                    # Teste Forecast
                    print(f"   🔮 Obtendo previsão...")
                    start = time.time()
                    forecast_result = await server.get_weather_forecast(location, "1h", None, "demo_user")
                    forecast_time = (time.time() - start) * 1000
                    print(f"   ✅ Forecast: {len(str(forecast_result.weather_data))} bytes | {forecast_time:.2f}ms | Cache: {forecast_result.cached}")
                
                self.results['tomorrow_io'] = {
                    'status': 'success',
                    'endpoints_tested': ['realtime', 'forecast'],
                    'response_time_avg': (realtime_time + forecast_time) / 2
                }
                
        except Exception as e:
            print(f"❌ Erro no Tomorrow.io: {e}")
            self.results['tomorrow_io'] = {'status': 'error', 'error': str(e)}
    
    async def test_anac_regulations_server(self):
        """Testa ANAC Regulations MCP Server"""
        print("\n" + "="*60)
        print("📋 TESTANDO ANAC REGULATIONS MCP SERVER")
        print("="*60)
        
        try:
            async with ANACRegulationsMCPServer() as server:
                # Teste com regulamentações
                print(f"\n📖 Obtendo informações de licenciamento...")
                start = time.time()
                
                licensing_result = await server.get_licensing_info("demo_user")
                
                response_time = (time.time() - start) * 1000
                print(f"✅ Licenciamento: {len(licensing_result.content)} caracteres")
                print(f"   🔗 URL: {licensing_result.url}")
                print(f"   ⏱️ Tempo: {response_time:.2f}ms | Cache: {licensing_result.cached}")
                
                # Teste RBAC específico
                print(f"\n📖 Obtendo RBAC 91...")
                start = time.time()
                
                rbac_result = await server.search_rbac("91", "demo_user")
                
                response_time = (time.time() - start) * 1000
                print(f"✅ RBAC 91: {len(rbac_result.content)} caracteres")
                print(f"   🔗 URL: {rbac_result.url}")
                print(f"   ⏱️ Tempo: {response_time:.2f}ms | Cache: {rbac_result.cached}")
                
                self.results['anac_regulations'] = {
                    'status': 'success',
                    'regulations_tested': ['licensing', 'rbac_91'],
                    'response_time_avg': response_time
                }
                
        except Exception as e:
            print(f"❌ Erro no ANAC Regulations: {e}")
            self.results['anac_regulations'] = {'status': 'error', 'error': str(e)}
    
    async def test_mcp_tools_interface(self):
        """Testa interface MCP Tools"""
        print("\n" + "="*60)
        print("🔧 TESTANDO MCP TOOLS INTERFACE")
        print("="*60)
        
        try:
            # Teste AirportDB tool
            print(f"\n🛫 Testando get_airport_info_tool...")
            start = time.time()
            airport_tool_result = await ADDITIONAL_MCP_TOOLS["get_airport_info"]("SBGR", "demo_user")
            tool_time = (time.time() - start) * 1000
            print(f"✅ AirportDB Tool: {airport_tool_result['icao_code']} | {tool_time:.2f}ms")
            
            # Teste Distance tool
            print(f"\n📏 Testando calculate_route_distance_tool...")
            start = time.time()
            distance_tool_result = await ADDITIONAL_MCP_TOOLS["calculate_route_distance"](["SBGR", "SBSP"], True, "demo_user")
            tool_time = (time.time() - start) * 1000
            print(f"✅ Distance Tool: {' -> '.join(distance_tool_result['route'])} | {tool_time:.2f}ms")
            
            # Teste Weather tool
            print(f"\n🌤️ Testando get_metar_avweather_tool...")
            start = time.time()
            weather_tool_result = await ADDITIONAL_MCP_TOOLS["get_metar_avweather"](["SBGR", "SBSP"], "json", "demo_user")
            tool_time = (time.time() - start) * 1000
            print(f"✅ Weather Tool: {weather_tool_result['data_type']} | {tool_time:.2f}ms")
            
            self.results['mcp_tools'] = {
                'status': 'success',
                'tools_tested': ['airportdb', 'distance', 'weather'],
                'response_time_avg': tool_time
            }
            
        except Exception as e:
            print(f"❌ Erro nos MCP Tools: {e}")
            self.results['mcp_tools'] = {'status': 'error', 'error': str(e)}
    
    async def run_all_tests(self):
        """Executa todos os testes"""
        print("🚀 INICIANDO DEMONSTRAÇÃO DOS 5 MCPs SERVERS ADICIONAIS")
        print("="*80)
        
        self.start_time = datetime.now(timezone.utc)
        
        # Executar todos os testes
        await self.test_airportdb_server()
        await self.test_distance_server()
        await self.test_aviation_weather_server()
        await self.test_tomorrow_io_server()
        await self.test_anac_regulations_server()
        await self.test_mcp_tools_interface()
        
        self.end_time = datetime.now(timezone.utc)
        
        # Relatório final
        await self.generate_report()
    
    async def generate_report(self):
        """Gera relatório final da demonstração"""
        print("\n" + "="*80)
        print("📊 RELATÓRIO FINAL DA DEMONSTRAÇÃO")
        print("="*80)
        
        total_duration = (self.end_time - self.start_time).total_seconds()
        
        print(f"\n⏱️ Tempo total de execução: {total_duration:.2f} segundos")
        print(f"🕐 Início: {self.start_time.strftime('%H:%M:%S')}")
        print(f"🕐 Fim: {self.end_time.strftime('%H:%M:%S')}")
        
        print(f"\n📈 RESULTADOS POR SERVIDOR:")
        print("-" * 50)
        
        success_count = 0
        error_count = 0
        
        for server_name, result in self.results.items():
            status_icon = "✅" if result['status'] == 'success' else "❌"
            print(f"{status_icon} {server_name.upper()}: {result['status']}")
            
            if result['status'] == 'success':
                success_count += 1
                if 'response_time_avg' in result:
                    print(f"   ⏱️ Tempo médio: {result['response_time_avg']:.2f}ms")
            else:
                error_count += 1
                print(f"   💥 Erro: {result.get('error', 'Desconhecido')}")
        
        print(f"\n🎯 RESUMO:")
        print(f"   ✅ Sucessos: {success_count}/6")
        print(f"   ❌ Erros: {error_count}/6")
        print(f"   📊 Taxa de sucesso: {(success_count/6)*100:.1f}%")
        
        if success_count == 6:
            print(f"\n🎉 TODOS OS 5 MCPs SERVERS ADICIONAIS ESTÃO FUNCIONANDO PERFEITAMENTE!")
            print(f"🚀 Sistema pronto para produção e integração com agentes!")
        else:
            print(f"\n⚠️ Alguns servidores apresentaram problemas. Verificar logs para detalhes.")
        
        print(f"\n" + "="*80)

async def main():
    """Função principal"""
    demo = AdditionalServersDemo()
    await demo.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main()) 