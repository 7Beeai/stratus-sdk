import asyncio
import aiohttp
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timezone, timedelta
import json
import hashlib
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from src.utils.logging import get_logger
from src.utils.base import CircuitBreaker, ExponentialBackoff, CacheManager
from config.settings import get_settings

logger = get_logger()
settings = get_settings()

class AISWEBArea(Enum):
    """AISWEB API areas"""
    SUPLEMENTOS = "suplementos"
    CARTAS = "cartas"
    CHECKLIST_AIRAC = "checklist_airac"
    AIP_PUBLICATION = "aip_publication"
    ROTAER_AIRPORTS = "rotaer_airports"
    ROTAER_DETAIL = "rotaer_detail"
    WAYPOINTS = "waypoints"
    PREFERRED_ROUTES = "preferred_routes"
    ROUTESP_AMDT = "routesp_amdt"
    NOTAM = "notam"
    GEILOC = "geiloc"
    INFOTEMP = "infotemp"
    SUNRISE_SUNSET = "sunrise_sunset"
    METAR_TAF = "metar_taf"

@dataclass
class AISWEBResponse:
    """Standard AISWEB response structure"""
    endpoint: str
    parameters: Dict[str, Any]
    data: Any
    retrieved_at: datetime
    cached: bool = False
    response_time_ms: float = 0.0
    
    def __post_init__(self):
        if self.retrieved_at is None:
            self.retrieved_at = datetime.now(timezone.utc)

class AISWEBMCPServer:
    """AISWEB MCP Server - Sistema Oficial DECEA para Informações Aeronáuticas"""
    
    def __init__(self):
        self.base_url = "https://aisweb.decea.mil.br/api/"
        self.api_key = "1133749630"
        self.api_pass = "50030a18-2198-11f0-a1fe-0050569ac2e1"
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            timeout_duration=15,
            half_open_max_calls=1
        )
        
        # Cache manager
        self.cache = CacheManager()
        
        # Retry logic
        self.backoff = ExponentialBackoff(
            initial_delay=1.0,
            max_delay=8.0,
            multiplier=2.0,
            jitter=True
        )
        
        # HTTP session
        self.session = None
        
        # Brazilian ICAO codes validation
        self.valid_icao_codes = {
            # Major airports
            'SBGR', 'SBSP', 'SBRJ', 'SBGL', 'SBBR', 'SBCF', 'SBRF', 'SBSV', 'SBFZ', 'SBCY',
            'SBPA', 'SBCT', 'SBBE', 'SBMN', 'SBVT', 'SBCG', 'SBFL', 'SBJP', 'SBMO', 'SBTE',
            # Regional airports (sample - add more as needed)
            'SBAA', 'SBAF', 'SBAQ', 'SBAR', 'SBAT', 'SBAU', 'SBAX', 'SBBU', 'SBCB', 'SBCD',
            'SBCH', 'SBCI', 'SBCJ', 'SBCM', 'SBCO', 'SBCP', 'SBCR', 'SBCS', 'SBCV', 'SBCW',
            'SBCX', 'SBCZ', 'SBDB', 'SBDC', 'SBDN', 'SBDO', 'SBDT', 'SBEG', 'SBEK', 'SBER',
            'SBFI', 'SBFN', 'SBFS', 'SBFT', 'SBGM', 'SBGO', 'SBGU', 'SBGV', 'SBGW', 'SBHT',
            'SBIC', 'SBIH', 'SBIL', 'SBIP', 'SBIS', 'SBIT', 'SBIZ', 'SBJF', 'SBJR', 'SBJV',
            'SBKG', 'SBKP', 'SBLB', 'SBLE', 'SBLJ', 'SBLN', 'SBLP', 'SBLS', 'SBLT', 'SBLV',
            'SBMA', 'SBMC', 'SBMD', 'SBME', 'SBMG', 'SBMK', 'SBML', 'SBMM', 'SBMP', 'SBMQ',
            'SBMS', 'SBMT', 'SBMY', 'SBNF', 'SBNM', 'SBNT', 'SBNV', 'SBOI', 'SBOK', 'SBOU',
            'SBPB', 'SBPC', 'SBPF', 'SBPJ', 'SBPK', 'SBPL', 'SBPN', 'SBPP', 'SBPR', 'SBPS',
            'SBPV', 'SBPZ', 'SBQV', 'SBRB', 'SBRE', 'SBRG', 'SBRP', 'SBRU', 'SBRW', 'SBSC',
            'SBSG', 'SBSI', 'SBSJ', 'SBSL', 'SBSM', 'SBSN', 'SBSO', 'SBSR', 'SBST', 'SBSW',
            'SBTB', 'SBTC', 'SBTD', 'SBTF', 'SBTG', 'SBTH', 'SBTI', 'SBTK', 'SBTL', 'SBTS',
            'SBTT', 'SBTU', 'SBTV', 'SBTX', 'SBUA', 'SBUF', 'SBUG', 'SBUL', 'SBUP', 'SBUR',
            'SBUV', 'SBVG', 'SBVH', 'SBVP', 'SBVR', 'SBWA', 'SBWI', 'SBYA', 'SBYB', 'SBYC',
            'SBYS', 'SBZM'
        }

    async def __aenter__(self):
        """Async context manager entry"""
        # Create HTTP session
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                'User-Agent': 'Stratus.IA/1.0 (Aviation Information System)',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        )
        
        logger.log_agent_action(
            agent_name="AISWEBMCPServer",
            action="initialize",
            message="Conectado ao AISWEB DECEA",
            user_id="system",
            success=True
        )
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    def _validate_icao_code(self, icao_code: str) -> bool:
        """Validate Brazilian ICAO code"""
        if not icao_code:
            return False
        
        icao_upper = icao_code.upper().strip()
        
        # Check format (SBxx)
        if not re.match(r'^SB[A-Z]{2}$', icao_upper):
            return False
        
        # Check against known codes (optional - can be disabled for flexibility)
        # return icao_upper in self.valid_icao_codes
        return True  # Allow all SBxx format codes

    def _sanitize_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize and validate parameters"""
        sanitized = {}
        
        for key, value in params.items():
            if value is None or value == "":
                continue
                
            # Convert to string and strip
            str_value = str(value).strip()
            
            # Skip empty values
            if not str_value:
                continue
            
            # Special handling for ICAO codes
            if key.lower() in ['icao', 'icaocode', 'aero', 'adep', 'ades']:
                if self._validate_icao_code(str_value):
                    sanitized[key] = str_value.upper()
                else:
                    logger.log_safety_violation(
                        violation_type="INVALID_ICAO_CODE",
                        message=f"Código ICAO inválido: {str_value}",
                        agent_name="AISWEBMCPServer",
                        user_id="system",
                        severity="MEDIUM"
                    )
                    continue
            
            # Special handling for dates
            elif key.lower() in ['dt', 'dt_i', 'dt_f', 'aip_dt']:
                # Validate date format (YYYY-MM-DD or YYYYMMDD)
                if re.match(r'^\d{4}-\d{2}-\d{2}$', str_value) or re.match(r'^\d{8}$', str_value):
                    sanitized[key] = str_value
                else:
                    logger.log_agent_action(
                        agent_name="AISWEBMCPServer",
                        action="validate_parameters",
                        message=f"Formato de data inválido: {key}={str_value}",
                        user_id="system",
                        success=False
                    )
                    continue
            
            # Special handling for numbers
            elif key.lower() in ['s', 'rowstart', 'rowend', 'number', 'serie', 'level', 'dist', 'nof', 'amdt']:
                try:
                    int_value = int(str_value)
                    if int_value >= 0:  # No negative numbers
                        sanitized[key] = str(int_value)
                except ValueError:
                    continue
            
            # Default: add as is
            else:
                sanitized[key] = str_value
        
        return sanitized

    def _generate_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate cache key for request"""
        key_data = {
            "endpoint": endpoint,
            "params": sorted(params.items())
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_cache_ttl(self, area: str) -> int:
        """Get cache TTL based on area criticality"""
        ttl_map = {
            "notam": 300,           # 5 minutes - critical operational
            "suplementos": 1800,    # 30 minutes - frequent updates
            "cartas": 14400,        # 4 hours - less frequent changes
            "rotaer_airports": 86400,    # 24 hours - static data
            "rotaer_detail": 86400,      # 24 hours - static data
            "waypoints": 43200,     # 12 hours - semi-static
            "preferred_routes": 21600,   # 6 hours - operational changes
            "sunrise_sunset": 86400,     # 24 hours - astronomical data
            "checklist_airac": 43200,    # 12 hours - AIRAC cycle
            "aip_publication": 43200,    # 12 hours - publications
            "geiloc": 86400,        # 24 hours - geographic data
            "infotemp": 3600,       # 1 hour - temporary info
            "routesp_amdt": 21600,  # 6 hours - route amendments
            "metar_taf": 1800       # 30 minutes - weather data
        }
        return ttl_map.get(area, 3600)  # Default 1 hour

    def _parse_response(self, response_text: str, content_type: str) -> Any:
        """Parse response based on content type"""
        if 'application/json' in content_type:
            return json.loads(response_text)
        elif 'text/xml' in content_type or 'application/xml' in content_type:
            # Parse XML and convert to dict-like structure
            try:
                root = ET.fromstring(response_text)
                return self._xml_to_dict(root)
            except ET.ParseError as e:
                logger.log_agent_action(
                    agent_name="AISWEBMCPServer",
                    action="parse_response",
                    message=f"Erro ao fazer parse XML: {str(e)}",
                    user_id="system",
                    success=False
                )
                return {"error": "XML parsing failed", "raw_response": response_text}
        else:
            # Try JSON first, then XML
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                try:
                    root = ET.fromstring(response_text)
                    return self._xml_to_dict(root)
                except ET.ParseError:
                    return {"error": "Unknown response format", "raw_response": response_text}

    def _xml_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """Convert XML element to dictionary"""
        result = {}
        
        # Add attributes
        if element.attrib:
            result['@attributes'] = element.attrib
        
        # Add text content
        if element.text and element.text.strip():
            result['text'] = element.text.strip()
        
        # Add child elements
        for child in element:
            child_data = self._xml_to_dict(child)
            if child.tag in result:
                # Multiple children with same tag
                if isinstance(result[child.tag], list):
                    result[child.tag].append(child_data)
                else:
                    result[child.tag] = [result[child.tag], child_data]
            else:
                result[child.tag] = child_data
        
        return result

    async def _make_request(self, area: str, additional_params: Dict[str, Any] = None, 
                           user_id: str = "system") -> AISWEBResponse:
        """Make request to AISWEB API with circuit breaker"""
        
        # Prepare parameters
        params = {
            "apiKey": self.api_key,
            "apiPass": self.api_pass,
            "area": area
        }
        
        if additional_params:
            sanitized_params = self._sanitize_parameters(additional_params)
            params.update(sanitized_params)
        
        # Generate cache key
        cache_key = self._generate_cache_key(area, params)
        
        # Check cache first
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            # Remove cached flag from cached_data to avoid duplication
            cached_data.pop('cached', None)
            return AISWEBResponse(**cached_data, cached=True)
        
        @self.circuit_breaker
        async def _request():
            start_time = datetime.now()
            
            try:
                # Make HTTP request
                async with self.session.get(self.base_url, params=params) as response:
                    response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
                    
                    if response.status == 200:
                        response_text = await response.text()
                        content_type = response.headers.get('content-type', '')
                        
                        # Parse response based on content type
                        data = self._parse_response(response_text, content_type)
                        
                        result = AISWEBResponse(
                            endpoint=area,
                            parameters=params,
                            data=data,
                            retrieved_at=datetime.now(timezone.utc),
                            response_time_ms=response_time_ms
                        )
                        
                        # Cache with appropriate TTL
                        ttl = self._get_cache_ttl(area)
                        await self.cache.set(cache_key, asdict(result), ttl)
                        
                        return result
                    
                    else:
                        error_text = await response.text()
                        raise Exception(f"HTTP {response.status}: {error_text}")
                        
            except Exception as e:
                logger.log_agent_action(
                    agent_name="AISWEBMCPServer",
                    action="make_request",
                    message=f"Erro na requisição para {area}: {str(e)}",
                    user_id=user_id,
                    success=False,
                    additional_context={"params": params}
                )
                raise
        
        # Retry logic with exponential backoff
        for attempt in range(3):
            try:
                result = await _request()
                
                # Log successful request
                logger.log_agent_action(
                    agent_name="AISWEBMCPServer",
                    action="make_request",
                    message=f"Requisição {area} realizada com sucesso em {result.response_time_ms:.1f}ms",
                    user_id=user_id,
                    success=True,
                    additional_context={
                        "area": area,
                        "params": params,
                        "response_time_ms": result.response_time_ms
                    }
                )
                
                return result
                
            except Exception as e:
                if attempt == 2:  # Last attempt
                    # Try to return stale cache if available
                    try:
                        stale_data = await self.cache.get(cache_key)
                        if stale_data:
                            logger.log_agent_action(
                                agent_name="AISWEBMCPServer",
                                action="fallback_cache",
                                message=f"Usando cache stale para {area} após falha",
                                user_id=user_id,
                                success=True
                            )
                            return AISWEBResponse(**stale_data, cached=True)
                    except Exception:
                        pass  # Ignore cache errors in fallback
                    
                    # Log critical failure
                    logger.log_safety_violation(
                        violation_type="AISWEB_API_FAILURE",
                        message=f"Falha crítica na API AISWEB para {area}: {str(e)}",
                        agent_name="AISWEBMCPServer",
                        user_id=user_id,
                        severity="HIGH"
                    )
                    raise
                
                delay = self.backoff.get_delay(attempt)
                await asyncio.sleep(delay)

    # ==================== SUPLEMENTOS E CARTAS ====================

    async def get_suplementos_aisweb(self, icao_code: str, suplemento_number: Optional[int] = None, 
                                    user_id: str = "system") -> AISWEBResponse:
        """Get AIS supplements for specific airport"""
        params = {"ICAO": icao_code}
        
        if suplemento_number is not None:
            params["s"] = suplemento_number
        
        return await self._make_request("suplementos", params, user_id)

    async def get_cartas_aisweb(self, area: str = "cartas", especie: Optional[str] = None,
                               tipo: Optional[str] = None, icao_code: Optional[str] = None,
                               name: Optional[str] = None, dt: Optional[str] = None,
                               indice_mapa: Optional[str] = None, use: Optional[str] = None,
                               user_id: str = "system") -> AISWEBResponse:
        """Get aeronautical charts"""
        params = {}
        
        if especie:
            params["especie"] = especie
        if tipo:
            params["tipo"] = tipo
        if icao_code:
            params["icaoCode"] = icao_code
        if name:
            params["name"] = name
        if dt:
            params["dt"] = dt
        if indice_mapa:
            params["indiceMapa"] = indice_mapa
        if use:
            params["use"] = use
        
        return await self._make_request(area, params, user_id)

    # ==================== PUBLICAÇÕES E AIRAC ====================

    async def get_checklist_airac(self, area: str = "checklist_airac", airac: Optional[str] = None,
                                 use: Optional[str] = None, user_id: str = "system") -> AISWEBResponse:
        """Get AIRAC publication checklist"""
        params = {}
        
        if airac:
            params["airac"] = airac
        if use:
            params["use"] = use
        
        return await self._make_request(area, params, user_id)

    async def get_aip_publication(self, area: str = "aip_publication", aip_type: Optional[str] = None,
                                 aip_dt: Optional[str] = None, user_id: str = "system") -> AISWEBResponse:
        """Get AIP publications"""
        params = {}
        
        if aip_type:
            params["type"] = aip_type
        if aip_dt:
            params["dt"] = aip_dt
        
        return await self._make_request(area, params, user_id)

    # ==================== ROTAER E AERÓDROMOS ====================

    async def search_rotaer_airports(self, area: str = "rotaer_airports", rowstart: Optional[int] = None,
                                    rowend: Optional[int] = None, aero: Optional[str] = None,
                                    name: Optional[str] = None, city: Optional[str] = None,
                                    uf: Optional[str] = None, type_aero: Optional[str] = None,
                                    use: Optional[str] = None, user_id: str = "system") -> AISWEBResponse:
        """Search ROTAER airports with multiple filters"""
        params = {}
        
        if rowstart is not None:
            params["rowstart"] = rowstart
        if rowend is not None:
            params["rowend"] = rowend
        if aero:
            params["aero"] = aero
        if name:
            params["name"] = name
        if city:
            params["city"] = city
        if uf:
            params["uf"] = uf
        if type_aero:
            params["type"] = type_aero
        if use:
            params["use"] = use
        
        return await self._make_request(area, params, user_id)

    async def get_rotaer_aero_detail(self, aero: str, area: str = "rotaer_detail",
                                    user_id: str = "system") -> AISWEBResponse:
        """Get detailed ROTAER airport information"""
        params = {"aero": aero}
        return await self._make_request(area, params, user_id)

    # ==================== NAVEGAÇÃO E ROTAS ====================

    async def list_waypoints(self, area: str = "waypoints", ident: Optional[str] = None,
                            type_wp: Optional[str] = None, feature: Optional[str] = None,
                            dist: Optional[int] = None, user_id: str = "system") -> AISWEBResponse:
        """List waypoints with filters"""
        params = {}
        
        if ident:
            params["ident"] = ident
        if type_wp:
            params["type"] = type_wp
        if feature:
            params["feature"] = feature
        if dist is not None:
            params["dist"] = dist
        
        return await self._make_request(area, params, user_id)

    async def search_preferred_routes(self, area: str = "preferred_routes", adep: Optional[str] = None,
                                     ades: Optional[str] = None, user_id: str = "system") -> AISWEBResponse:
        """Search preferred routes between airports"""
        params = {}
        
        if adep:
            params["adep"] = adep
        if ades:
            params["ades"] = ades
        
        return await self._make_request(area, params, user_id)

    async def get_routesp_next_amdt(self, area: str = "routesp_amdt", user_id: str = "system") -> AISWEBResponse:
        """Get next special routes amendments"""
        return await self._make_request(area, {}, user_id)

    # ==================== INFORMAÇÕES OPERACIONAIS ====================

    async def search_notam(self, area: str = "notam", icao_code: Optional[str] = None,
                          serie: Optional[int] = None, number: Optional[int] = None,
                          status: Optional[str] = None, dt_i: Optional[str] = None,
                          dt_f: Optional[str] = None, user_id: str = "system") -> AISWEBResponse:
        """Search NOTAMs with multiple filters"""
        params = {}
        
        if icao_code:
            params["icaoCode"] = icao_code
        if serie is not None:
            params["serie"] = serie
        if number is not None:
            params["number"] = number
        if status:
            params["status"] = status
        if dt_i:
            params["dt_i"] = dt_i
        if dt_f:
            params["dt_f"] = dt_f
        
        return await self._make_request(area, params, user_id)

    async def search_geiloc(self, area: str = "geiloc", ident: Optional[str] = None,
                           user_id: str = "system") -> AISWEBResponse:
        """Search geographic location information"""
        params = {}
        
        if ident:
            params["ident"] = ident
        
        return await self._make_request(area, params, user_id)

    async def search_infotemp(self, area: str = "infotemp", categoria: Optional[str] = None,
                             level: Optional[int] = None, user_id: str = "system") -> AISWEBResponse:
        """Search temporary information"""
        params = {}
        
        if categoria:
            params["categoria"] = categoria
        if level is not None:
            params["level"] = level
        
        return await self._make_request(area, params, user_id)

    async def get_sunrise_sunset(self, icao_code: str, area: str = "sunrise_sunset",
                                dt: Optional[str] = None, nof: Optional[int] = None,
                                user_id: str = "system") -> AISWEBResponse:
        """Get sunrise/sunset times for airport"""
        params = {"icaoCode": icao_code}
        
        if dt:
            params["dt"] = dt
        if nof is not None:
            params["nof"] = nof
        
        return await self._make_request(area, params, user_id)

    # ==================== DADOS METEOROLÓGICOS ====================

    async def get_metar_taf(self, icao_code: str, area: str = "metar_taf",
                           user_id: str = "system") -> AISWEBResponse:
        """Get METAR and TAF data (complementary to REDEMET)"""
        params = {"icaoCode": icao_code}
        return await self._make_request(area, params, user_id)

# ==================== MCP TOOLS INTERFACE ====================

async def get_suplementos_aisweb_tool(icao_code: str, suplemento_number: Optional[int] = None,
                                     user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting AIS supplements"""
    async with AISWEBMCPServer() as server:
        result = await server.get_suplementos_aisweb(icao_code, suplemento_number, user_id)
        return asdict(result)

async def get_cartas_aisweb_tool(area: str = "cartas", especie: Optional[str] = None,
                                tipo: Optional[str] = None, icao_code: Optional[str] = None,
                                name: Optional[str] = None, dt: Optional[str] = None,
                                indice_mapa: Optional[str] = None, use: Optional[str] = None,
                                user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting aeronautical charts"""
    async with AISWEBMCPServer() as server:
        result = await server.get_cartas_aisweb(area, especie, tipo, icao_code, name, dt, indice_mapa, use, user_id)
        return asdict(result)

async def get_checklist_airac_tool(area: str = "checklist_airac", airac: Optional[str] = None,
                                  use: Optional[str] = None, user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting AIRAC checklist"""
    async with AISWEBMCPServer() as server:
        result = await server.get_checklist_airac(area, airac, use, user_id)
        return asdict(result)

async def get_aip_publication_tool(area: str = "aip_publication", aip_type: Optional[str] = None,
                                  aip_dt: Optional[str] = None, user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting AIP publications"""
    async with AISWEBMCPServer() as server:
        result = await server.get_aip_publication(area, aip_type, aip_dt, user_id)
        return asdict(result)

async def search_rotaer_airports_tool(area: str = "rotaer_airports", rowstart: Optional[int] = None,
                                     rowend: Optional[int] = None, aero: Optional[str] = None,
                                     name: Optional[str] = None, city: Optional[str] = None,
                                     uf: Optional[str] = None, type_aero: Optional[str] = None,
                                     use: Optional[str] = None, user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for searching ROTAER airports"""
    async with AISWEBMCPServer() as server:
        result = await server.search_rotaer_airports(area, rowstart, rowend, aero, name, city, uf, type_aero, use, user_id)
        return asdict(result)

async def get_rotaer_aero_detail_tool(aero: str, area: str = "rotaer_detail",
                                     user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting ROTAER airport details"""
    async with AISWEBMCPServer() as server:
        result = await server.get_rotaer_aero_detail(aero, area, user_id)
        return asdict(result)

async def list_waypoints_tool(area: str = "waypoints", ident: Optional[str] = None,
                             type_wp: Optional[str] = None, feature: Optional[str] = None,
                             dist: Optional[int] = None, user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for listing waypoints"""
    async with AISWEBMCPServer() as server:
        result = await server.list_waypoints(area, ident, type_wp, feature, dist, user_id)
        return asdict(result)

async def search_preferred_routes_tool(area: str = "preferred_routes", adep: Optional[str] = None,
                                      ades: Optional[str] = None, user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for searching preferred routes"""
    async with AISWEBMCPServer() as server:
        result = await server.search_preferred_routes(area, adep, ades, user_id)
        return asdict(result)

async def get_routesp_next_amdt_tool(area: str = "routesp_amdt", user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting next route amendments"""
    async with AISWEBMCPServer() as server:
        result = await server.get_routesp_next_amdt(area, user_id)
        return asdict(result)

async def search_notam_tool(area: str = "notam", icao_code: Optional[str] = None,
                           serie: Optional[int] = None, number: Optional[int] = None,
                           status: Optional[str] = None, dt_i: Optional[str] = None,
                           dt_f: Optional[str] = None, user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for searching NOTAMs"""
    async with AISWEBMCPServer() as server:
        result = await server.search_notam(area, icao_code, serie, number, status, dt_i, dt_f, user_id)
        return asdict(result)

async def search_geiloc_tool(area: str = "geiloc", ident: Optional[str] = None,
                            user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for searching geographic locations"""
    async with AISWEBMCPServer() as server:
        result = await server.search_geiloc(area, ident, user_id)
        return asdict(result)

async def search_infotemp_tool(area: str = "infotemp", categoria: Optional[str] = None,
                              level: Optional[int] = None, user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for searching temporary information"""
    async with AISWEBMCPServer() as server:
        result = await server.search_infotemp(area, categoria, level, user_id)
        return asdict(result)

async def get_sunrise_sunset_tool(icao_code: str, area: str = "sunrise_sunset",
                                 dt: Optional[str] = None, nof: Optional[int] = None,
                                 user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting sunrise/sunset times"""
    async with AISWEBMCPServer() as server:
        result = await server.get_sunrise_sunset(icao_code, area, dt, nof, user_id)
        return asdict(result)

async def get_metar_taf_tool(icao_code: str, area: str = "metar_taf",
                            user_id: str = "system") -> Dict[str, Any]:
    """MCP tool for getting METAR/TAF data"""
    async with AISWEBMCPServer() as server:
        result = await server.get_metar_taf(icao_code, area, user_id)
        return asdict(result)

# Export ALL MCP tools
MCP_TOOLS = {
    # Suplementos e Cartas (2)
    "get_suplementos_aisweb": get_suplementos_aisweb_tool,
    "get_cartas_aisweb": get_cartas_aisweb_tool,
    
    # Publicações e AIRAC (2)
    "get_checklist_airac": get_checklist_airac_tool,
    "get_aip_publication": get_aip_publication_tool,
    
    # ROTAER e Aeródromos (2)
    "search_rotaer_airports": search_rotaer_airports_tool,
    "get_rotaer_aero_detail": get_rotaer_aero_detail_tool,
    
    # Navegação e Rotas (3)
    "list_waypoints": list_waypoints_tool,
    "search_preferred_routes": search_preferred_routes_tool,
    "get_routesp_next_amdt": get_routesp_next_amdt_tool,
    
    # Informações Operacionais (4)
    "search_notam": search_notam_tool,
    "search_geiloc": search_geiloc_tool,
    "search_infotemp": search_infotemp_tool,
    "get_sunrise_sunset": get_sunrise_sunset_tool,
    
    # Dados Meteorológicos (1)
    "get_metar_taf": get_metar_taf_tool
} 