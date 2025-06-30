import asyncio
import aiohttp
import json
import hashlib
import re
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode, quote
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

from src.utils.logging import get_logger
from src.utils.base import CircuitBreaker, ExponentialBackoff, CacheManager
from config.settings import get_settings

logger = get_logger()
settings = get_settings()

# ==================== AIRPORTDB MCP SERVER ====================

@dataclass
class AirportDBResponse:
    """AirportDB response structure"""
    icao_code: str
    airport_data: Dict[str, Any]
    retrieved_at: datetime
    cached: bool = False
    response_time_ms: float = 0.0

class AirportDBMCPServer:
    """AirportDB MCP Server - Dados Detalhados de Aeródromos"""
    
    def __init__(self):
        self.base_url = "https://airportdb.io/api/v1/airport"
        self.api_token = "e68427ec6114a121f153bc2a830b449b6909862bc409db283ce19a813194d8c6125525efc07afd6f2f4c6d737702e969"
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_duration=15)
        self.cache = CacheManager()
        self.session = None

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={'User-Agent': 'Stratus.IA/1.0 (Aviation Information System)'}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _validate_icao_code(self, icao_code: str) -> bool:
        """Validate ICAO code format"""
        if not icao_code or len(icao_code) != 4:
            return False
        return re.match(r'^[A-Z]{4}$', icao_code.upper()) is not None

    async def get_airport_info(self, icao_code: str, user_id: str = "system") -> AirportDBResponse:
        """Get detailed airport information"""
        icao_upper = icao_code.upper().strip()
        
        if not self._validate_icao_code(icao_upper):
            raise ValueError(f"Código ICAO inválido: {icao_code}")
        
        cache_key = f"airportdb_{icao_upper}"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return AirportDBResponse(**cached_data, cached=True)
        
        @self.circuit_breaker
        async def _request():
            start_time = datetime.now()
            url = f"{self.base_url}/{icao_upper}?apiToken={self.api_token}"
            
            async with self.session.get(url) as response:
                response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                if response.status == 200:
                    data = await response.json()
                    
                    result = AirportDBResponse(
                        icao_code=icao_upper,
                        airport_data=data,
                        retrieved_at=datetime.now(timezone.utc),
                        response_time_ms=response_time_ms
                    )
                    
                    # Cache for 24 hours (static data)
                    await self.cache.set(cache_key, asdict(result), 86400)
                    
                    logger.log_agent_action(
                        agent_name="AirportDBMCPServer",
                        action="get_airport_info",
                        message=f"Dados do aeródromo {icao_upper} obtidos com sucesso",
                        user_id=user_id,
                        success=True,
                        additional_context={"icao": icao_upper, "response_time_ms": response_time_ms}
                    )
                    
                    return result
                else:
                    error_text = await response.text()
                    raise Exception(f"HTTP {response.status}: {error_text}")
        
        return await _request()

# ==================== RAPIDAPI DISTANCE MCP SERVER ====================

@dataclass
class DistanceResponse:
    """Distance calculation response"""
    route: List[str]
    distance_data: Dict[str, Any]
    retrieved_at: datetime
    cached: bool = False
    response_time_ms: float = 0.0

class RapidAPIDistanceMCPServer:
    """RapidAPI Distance MCP Server - Cálculo de Distâncias"""
    
    def __init__(self):
        self.base_url = "https://distanceto.p.rapidapi.com/distance/route"
        self.api_key = "f8336cb822msh317be2d22bae78fp1d9387jsn37cf7647be6c"
        self.api_host = "distanceto.p.rapidapi.com"
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_duration=15)
        self.cache = CacheManager()
        self.session = None

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                'User-Agent': 'Stratus.IA/1.0 (Aviation Information System)',
                'Content-Type': 'application/json',
                'X-RapidAPI-Key': self.api_key,
                'X-RapidAPI-Host': self.api_host
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def calculate_route_distance(self, route: Union[str, List[str]], flight: bool = True, 
                                     user_id: str = "system") -> DistanceResponse:
        """Calculate distance for route"""
        if isinstance(route, str):
            route_list = [code.strip().upper() for code in route.split(',')]
        else:
            route_list = [code.strip().upper() for code in route]
        
        # Validate ICAO codes
        for code in route_list:
            if not re.match(r'^[A-Z]{4}$', code):
                raise ValueError(f"Código ICAO inválido na rota: {code}")
        
        cache_key = f"distance_{'_'.join(route_list)}_{flight}"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return DistanceResponse(**cached_data, cached=True)
        
        @self.circuit_breaker
        async def _request():
            start_time = datetime.now()
            
            # Format route for API
            route_data = [{"country": "BR", "name": code} for code in route_list]
            payload = {"route": route_data}
            
            async with self.session.post(self.base_url, json=payload) as response:
                response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                if response.status == 200:
                    data = await response.json()
                    
                    result = DistanceResponse(
                        route=route_list,
                        distance_data=data,
                        retrieved_at=datetime.now(timezone.utc),
                        response_time_ms=response_time_ms
                    )
                    
                    # Cache for 12 hours (semi-static data)
                    await self.cache.set(cache_key, asdict(result), 43200)
                    
                    logger.log_agent_action(
                        agent_name="RapidAPIDistanceMCPServer",
                        action="calculate_route_distance",
                        message=f"Distância calculada para rota {' -> '.join(route_list)}",
                        user_id=user_id,
                        success=True,
                        additional_context={"route": route_list, "response_time_ms": response_time_ms}
                    )
                    
                    return result
                else:
                    error_text = await response.text()
                    raise Exception(f"HTTP {response.status}: {error_text}")
        
        return await _request()

# ==================== AVIATION WEATHER GOV MCP SERVER ====================

@dataclass
class AvWeatherResponse:
    """Aviation Weather Gov response"""
    data_type: str
    stations: List[str]
    weather_data: Union[List[Dict], Dict[str, Any]]
    retrieved_at: datetime
    cached: bool = False
    response_time_ms: float = 0.0

class AviationWeatherGovMCPServer:
    """Aviation Weather Gov MCP Server - Dados Meteorológicos FAA"""
    
    def __init__(self):
        self.base_url = "https://aviationweather.gov/api/data"
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_duration=15)
        self.cache = CacheManager()
        self.session = None
        
        # Available endpoints
        self.endpoints = {
            'metar': {'ttl': 1800, 'format': 'json'},      # 30 min
            'taf': {'ttl': 3600, 'format': 'json'},        # 1 hour
            'pirep': {'ttl': 1800, 'format': 'json'},      # 30 min
            'isigmet': {'ttl': 600, 'format': 'json'},     # 10 min (critical)
            'windtemp': {'ttl': 3600, 'format': 'json'}    # 1 hour
        }

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={'User-Agent': 'Stratus.IA/1.0 (Aviation Information System)'}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _get_weather_data(self, endpoint: str, stations: Union[str, List[str]], 
                               format_type: str = "json", user_id: str = "system") -> AvWeatherResponse:
        """Generic method for weather data"""
        if endpoint not in self.endpoints:
            raise ValueError(f"Endpoint inválido: {endpoint}")
        
        if isinstance(stations, str):
            stations_list = [s.strip().upper() for s in stations.split(',')]
        else:
            stations_list = [s.strip().upper() for s in stations]
        
        stations_str = ','.join(stations_list)
        cache_key = f"avweather_{endpoint}_{stations_str}_{format_type}"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return AvWeatherResponse(**cached_data, cached=True)
        
        @self.circuit_breaker
        async def _request():
            start_time = datetime.now()
            
            params = {
                'ids': stations_str,
                'format': format_type
            }
            
            url = f"{self.base_url}/{endpoint}"
            async with self.session.get(url, params=params) as response:
                response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                if response.status == 200:
                    if format_type == 'json':
                        data = await response.json()
                    else:
                        data = await response.text()
                    
                    result = AvWeatherResponse(
                        data_type=endpoint,
                        stations=stations_list,
                        weather_data=data,
                        retrieved_at=datetime.now(timezone.utc),
                        response_time_ms=response_time_ms
                    )
                    
                    # Cache with endpoint-specific TTL
                    ttl = self.endpoints[endpoint]['ttl']
                    await self.cache.set(cache_key, asdict(result), ttl)
                    
                    logger.log_agent_action(
                        agent_name="AviationWeatherGovMCPServer",
                        action=f"get_{endpoint}",
                        message=f"Dados {endpoint.upper()} obtidos para {stations_str}",
                        user_id=user_id,
                        success=True,
                        additional_context={"endpoint": endpoint, "stations": stations_list, "response_time_ms": response_time_ms}
                    )
                    
                    return result
                else:
                    error_text = await response.text()
                    raise Exception(f"HTTP {response.status}: {error_text}")
        
        return await _request()

    async def get_metar(self, stations: Union[str, List[str]], format_type: str = "json", 
                       user_id: str = "system") -> AvWeatherResponse:
        """Get METAR data"""
        return await self._get_weather_data("metar", stations, format_type, user_id)

    async def get_taf(self, stations: Union[str, List[str]], format_type: str = "json", 
                     user_id: str = "system") -> AvWeatherResponse:
        """Get TAF data"""
        return await self._get_weather_data("taf", stations, format_type, user_id)

    async def get_pirep(self, stations: Union[str, List[str]], format_type: str = "json", 
                       user_id: str = "system") -> AvWeatherResponse:
        """Get PIREP data"""
        return await self._get_weather_data("pirep", stations, format_type, user_id)

    async def get_isigmet(self, stations: Union[str, List[str]], format_type: str = "json", 
                         user_id: str = "system") -> AvWeatherResponse:
        """Get International SIGMET data"""
        return await self._get_weather_data("isigmet", stations, format_type, user_id)

    async def get_windtemp(self, stations: Union[str, List[str]], format_type: str = "json", 
                          user_id: str = "system") -> AvWeatherResponse:
        """Get Wind/Temperature data"""
        return await self._get_weather_data("windtemp", stations, format_type, user_id)

# ==================== TOMORROW.IO WEATHER MCP SERVER ====================

@dataclass
class TomorrowIOResponse:
    """Tomorrow.io weather response"""
    endpoint: str
    location: Optional[str]
    weather_data: Dict[str, Any]
    retrieved_at: datetime
    cached: bool = False
    response_time_ms: float = 0.0

class TomorrowIOMCPServer:
    """Tomorrow.io MCP Server - Dados Meteorológicos Avançados"""
    
    def __init__(self):
        self.base_url = "https://api.tomorrow.io/v4"
        self.api_key = "FU1qyPelJIB46sGTZfzsAv35toSq8hSk"
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_duration=15)
        self.cache = CacheManager()
        self.session = None
        
        # Available endpoints with TTLs
        self.endpoints = {
            'realtime': {'ttl': 900, 'path': '/weather/realtime'},      # 15 min
            'forecast': {'ttl': 3600, 'path': '/weather/forecast'},     # 1 hour
            'history': {'ttl': 86400, 'path': '/weather/history'},      # 24 hours
            'timelines': {'ttl': 3600, 'path': '/timelines'},           # 1 hour
            'maps': {'ttl': 1800, 'path': '/weather/maps'}              # 30 min
        }

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                'User-Agent': 'Stratus.IA/1.0 (Aviation Information System)',
                'Content-Type': 'application/json'
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _validate_location(self, location: str) -> bool:
        """Validate location format (lat,lon or ICAO)"""
        # Check if it's coordinates (lat,lon)
        if ',' in location:
            try:
                lat, lon = location.split(',')
                float(lat.strip())
                float(lon.strip())
                return True
            except ValueError:
                return False
        
        # Check if it's ICAO code
        return re.match(r'^[A-Z]{4}$', location.upper()) is not None

    async def _make_weather_request(self, endpoint: str, location: str, 
                                   additional_params: Dict[str, Any] = None,
                                   user_id: str = "system") -> TomorrowIOResponse:
        """Generic weather request method"""
        if endpoint not in self.endpoints:
            raise ValueError(f"Endpoint inválido: {endpoint}")
        
        if not self._validate_location(location):
            raise ValueError(f"Localização inválida: {location}")
        
        cache_key = f"tomorrow_{endpoint}_{location}_{hash(str(additional_params))}"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return TomorrowIOResponse(**cached_data, cached=True)
        
        @self.circuit_breaker
        async def _request():
            start_time = datetime.now()
            
            params = {
                'apikey': self.api_key,
                'location': location
            }
            
            if additional_params:
                params.update(additional_params)
            
            url = f"{self.base_url}{self.endpoints[endpoint]['path']}"
            async with self.session.get(url, params=params) as response:
                response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                if response.status == 200:
                    data = await response.json()
                    
                    result = TomorrowIOResponse(
                        endpoint=endpoint,
                        location=location,
                        weather_data=data,
                        retrieved_at=datetime.now(timezone.utc),
                        response_time_ms=response_time_ms
                    )
                    
                    # Cache with endpoint-specific TTL
                    ttl = self.endpoints[endpoint]['ttl']
                    await self.cache.set(cache_key, asdict(result), ttl)
                    
                    logger.log_agent_action(
                        agent_name="TomorrowIOMCPServer",
                        action=f"get_{endpoint}",
                        message=f"Dados {endpoint} obtidos para {location}",
                        user_id=user_id,
                        success=True,
                        additional_context={"endpoint": endpoint, "location": location, "response_time_ms": response_time_ms}
                    )
                    
                    return result
                else:
                    error_text = await response.text()
                    raise Exception(f"HTTP {response.status}: {error_text}")
        
        return await _request()

    async def get_realtime_weather(self, location: str, fields: List[str] = None, 
                                  user_id: str = "system") -> TomorrowIOResponse:
        """Get realtime weather data"""
        params = {}
        if fields:
            params['fields'] = ','.join(fields)
        
        return await self._make_weather_request("realtime", location, params, user_id)

    async def get_weather_forecast(self, location: str, timesteps: str = "1h", 
                                  fields: List[str] = None, user_id: str = "system") -> TomorrowIOResponse:
        """Get weather forecast"""
        params = {'timesteps': timesteps}
        if fields:
            params['fields'] = ','.join(fields)
        
        return await self._make_weather_request("forecast", location, params, user_id)

    async def get_weather_history(self, location: str, start_time: str, end_time: str,
                                 timesteps: str = "1h", fields: List[str] = None,
                                 user_id: str = "system") -> TomorrowIOResponse:
        """Get historical weather data"""
        params = {
            'startTime': start_time,
            'endTime': end_time,
            'timesteps': timesteps
        }
        if fields:
            params['fields'] = ','.join(fields)
        
        return await self._make_weather_request("history", location, params, user_id)

    async def get_weather_timelines(self, location: str, fields: List[str], 
                                   timesteps: List[str] = None, user_id: str = "system") -> TomorrowIOResponse:
        """Get weather timelines"""
        params = {
            'fields': ','.join(fields)
        }
        if timesteps:
            params['timesteps'] = ','.join(timesteps)
        
        return await self._make_weather_request("timelines", location, params, user_id)

    async def get_weather_maps(self, location: str, map_type: str = "temperature",
                              user_id: str = "system") -> TomorrowIOResponse:
        """Get weather maps"""
        params = {'type': map_type}
        return await self._make_weather_request("maps", location, params, user_id)

# ==================== ANAC REGULATIONS MCP SERVER ====================

@dataclass
class ANACRegulationResponse:
    """ANAC regulation response"""
    regulation_type: str
    regulation_number: Optional[str]
    content: str
    url: str
    retrieved_at: datetime
    cached: bool = False

class ANACRegulationsMCPServer:
    """ANAC Regulations MCP Server - Regulamentações Brasileiras"""
    
    def __init__(self):
        self.base_url = "https://www.gov.br/anac/pt-br"
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_duration=30)
        self.cache = CacheManager()
        self.session = None
        
        # Known regulation URLs
        self.regulation_urls = {
            'rbac': '/assuntos/legislacao/legislacao-1/rbha-e-rbac/rbac',
            'is': '/assuntos/legislacao/legislacao-1/instrucoes-suplementares',
            'licencas': '/assuntos/pessoas-e-empresas/profissionais-da-aviacao-civil/licencas-e-habilitacoes',
            'certificacao': '/assuntos/aeronaves/certificacao-de-aeronaves'
        }

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=60, connect=15)
        # Configuração SSL personalizada para resolver problemas de certificado
        connector = aiohttp.TCPConnector(ssl=False)  # Desabilita verificação SSL para gov.br
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_regulation_content(self, regulation_type: str, regulation_number: Optional[str] = None,
                                   user_id: str = "system") -> ANACRegulationResponse:
        """Get ANAC regulation content"""
        if regulation_type not in self.regulation_urls:
            raise ValueError(f"Tipo de regulamentação inválido: {regulation_type}")
        
        cache_key = f"anac_{regulation_type}_{regulation_number or 'general'}"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return ANACRegulationResponse(**cached_data, cached=True)
        
        @self.circuit_breaker
        async def _request():
            url_path = self.regulation_urls[regulation_type]
            if regulation_number:
                url_path += f"/{regulation_type}-{regulation_number}"
            
            full_url = f"{self.base_url}{url_path}"
            
            async with self.session.get(full_url) as response:
                if response.status == 200:
                    html_content = await response.text()
                    
                    # Parse HTML content
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Extract main content
                    content_div = soup.find('div', class_='content') or soup.find('main') or soup.find('article')
                    if content_div:
                        # Remove scripts and styles
                        for script in content_div(["script", "style"]):
                            script.decompose()
                        
                        content = content_div.get_text(separator='\n', strip=True)
                    else:
                        content = soup.get_text(separator='\n', strip=True)
                    
                    # Clean up content
                    lines = [line.strip() for line in content.split('\n') if line.strip()]
                    cleaned_content = '\n'.join(lines)
                    
                    result = ANACRegulationResponse(
                        regulation_type=regulation_type,
                        regulation_number=regulation_number,
                        content=cleaned_content,
                        url=full_url,
                        retrieved_at=datetime.now(timezone.utc)
                    )
                    
                    # Cache for 24 hours (regulations don't change frequently)
                    await self.cache.set(cache_key, asdict(result), 86400)
                    
                    logger.log_agent_action(
                        agent_name="ANACRegulationsMCPServer",
                        action="get_regulation_content",
                        message=f"Regulamentação {regulation_type.upper()} {regulation_number or ''} obtida",
                        user_id=user_id,
                        success=True,
                        additional_context={"regulation_type": regulation_type, "regulation_number": regulation_number}
                    )
                    
                    return result
                else:
                    error_text = await response.text()
                    raise Exception(f"HTTP {response.status}: {error_text}")
        
        return await _request()

    async def search_rbac(self, rbac_number: str, user_id: str = "system") -> ANACRegulationResponse:
        """Search specific RBAC regulation"""
        return await self.get_regulation_content("rbac", rbac_number, user_id)

    async def get_licensing_info(self, user_id: str = "system") -> ANACRegulationResponse:
        """Get licensing and certification information"""
        return await self.get_regulation_content("licencas", None, user_id)

# ==================== MCP TOOLS INTERFACE ====================

# AirportDB Tools
async def get_airport_info_tool(icao_code: str, user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting airport information"""
    async with AirportDBMCPServer() as server:
        result = await server.get_airport_info(icao_code, user_id)
        return asdict(result)

# Distance Tools
async def calculate_route_distance_tool(route: Union[str, List[str]], flight: bool = True, 
                                       user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for calculating route distances"""
    async with RapidAPIDistanceMCPServer() as server:
        result = await server.calculate_route_distance(route, flight, user_id)
        return asdict(result)

# Aviation Weather Gov Tools
async def get_metar_avweather_tool(stations: Union[str, List[str]], format_type: str = "json", 
                                  user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting METAR from Aviation Weather Gov"""
    async with AviationWeatherGovMCPServer() as server:
        result = await server.get_metar(stations, format_type, user_id)
        return asdict(result)

async def get_taf_avweather_tool(stations: Union[str, List[str]], format_type: str = "json", 
                                user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting TAF from Aviation Weather Gov"""
    async with AviationWeatherGovMCPServer() as server:
        result = await server.get_taf(stations, format_type, user_id)
        return asdict(result)

async def get_pirep_tool(stations: Union[str, List[str]], format_type: str = "json", 
                        user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting PIREP data"""
    async with AviationWeatherGovMCPServer() as server:
        result = await server.get_pirep(stations, format_type, user_id)
        return asdict(result)

async def get_isigmet_tool(stations: Union[str, List[str]], format_type: str = "json", 
                          user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting International SIGMET data"""
    async with AviationWeatherGovMCPServer() as server:
        result = await server.get_isigmet(stations, format_type, user_id)
        return asdict(result)

async def get_windtemp_tool(stations: Union[str, List[str]], format_type: str = "json", 
                           user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting Wind/Temperature data"""
    async with AviationWeatherGovMCPServer() as server:
        result = await server.get_windtemp(stations, format_type, user_id)
        return asdict(result)

# Tomorrow.io Tools
async def get_realtime_weather_tool(location: str, fields: List[str] = None, 
                                   user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting realtime weather"""
    async with TomorrowIOMCPServer() as server:
        result = await server.get_realtime_weather(location, fields, user_id)
        return asdict(result)

async def get_weather_forecast_tool(location: str, timesteps: str = "1h", 
                                   fields: List[str] = None, user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting weather forecast"""
    async with TomorrowIOMCPServer() as server:
        result = await server.get_weather_forecast(location, timesteps, fields, user_id)
        return asdict(result)

async def get_weather_history_tool(location: str, start_time: str, end_time: str,
                                  timesteps: str = "1h", fields: List[str] = None,
                                  user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting historical weather"""
    async with TomorrowIOMCPServer() as server:
        result = await server.get_weather_history(location, start_time, end_time, timesteps, fields, user_id)
        return asdict(result)

async def get_weather_timelines_tool(location: str, fields: List[str], 
                                    timesteps: List[str] = None, user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting weather timelines"""
    async with TomorrowIOMCPServer() as server:
        result = await server.get_weather_timelines(location, fields, timesteps, user_id)
        return asdict(result)

async def get_weather_maps_tool(location: str, map_type: str = "temperature",
                               user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting weather maps"""
    async with TomorrowIOMCPServer() as server:
        result = await server.get_weather_maps(location, map_type, user_id)
        return asdict(result)

# ANAC Regulation Tools
async def search_rbac_tool(rbac_number: str, user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for searching RBAC regulations"""
    async with ANACRegulationsMCPServer() as server:
        result = await server.search_rbac(rbac_number, user_id)
        return asdict(result)

async def get_licensing_info_tool(user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting licensing information"""
    async with ANACRegulationsMCPServer() as server:
        result = await server.get_licensing_info(user_id)
        return asdict(result)

async def get_regulation_content_tool(regulation_type: str, regulation_number: Optional[str] = None,
                                     user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting regulation content"""
    async with ANACRegulationsMCPServer() as server:
        result = await server.get_regulation_content(regulation_type, regulation_number, user_id)
        return asdict(result)

# Export ALL MCP tools
ADDITIONAL_MCP_TOOLS = {
    # AirportDB (1 tool)
    "get_airport_info": get_airport_info_tool,
    
    # Distance Calculation (1 tool)
    "calculate_route_distance": calculate_route_distance_tool,
    
    # Aviation Weather Gov (5 tools)
    "get_metar_avweather": get_metar_avweather_tool,
    "get_taf_avweather": get_taf_avweather_tool,
    "get_pirep": get_pirep_tool,
    "get_isigmet": get_isigmet_tool,
    "get_windtemp": get_windtemp_tool,
    
    # Tomorrow.io Weather (5 tools)
    "get_realtime_weather": get_realtime_weather_tool,
    "get_weather_forecast": get_weather_forecast_tool,
    "get_weather_history": get_weather_history_tool,
    "get_weather_timelines": get_weather_timelines_tool,
    "get_weather_maps": get_weather_maps_tool,
    
    # ANAC Regulations (3 tools)
    "search_rbac": search_rbac_tool,
    "get_licensing_info": get_licensing_info_tool,
    "get_regulation_content": get_regulation_content_tool
} 