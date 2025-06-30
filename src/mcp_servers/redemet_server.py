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

from src.utils.logging import get_logger
from src.utils.base import CircuitBreaker, ExponentialBackoff, CacheManager
from config.settings import get_settings

logger = get_logger()
settings = get_settings()

class RedemetDataType(Enum):
    AERODROMOS = "aerodromos"
    AERODROMOS_STATUS = "aerodromos_status"
    AERODROMOS_INFO = "aerodromos_info"
    METAR = "metar"
    TAF = "taf"
    SIGMET = "sigmet"
    GAMET = "gamet"
    PILOT = "pilot"
    TEMP = "temp"
    AVISO = "aviso"
    METEOGRAMA = "meteograma"
    AMDAR = "amdar"
    MODELO = "modelo"
    RADAR = "radar"
    SATELITE = "satelite"
    SIGWX = "sigwx"
    STSC = "stsc"

@dataclass
class RedemetResponse:
    data_type: RedemetDataType
    raw_data: Dict[str, Any]
    processed_data: Dict[str, Any]
    source: str = "REDEMET"
    retrieved_at: datetime = None
    cache_hit: bool = False
    def __post_init__(self):
        if self.retrieved_at is None:
            self.retrieved_at = datetime.now(timezone.utc)

class RedemetMCPServer:
    def __init__(self):
        self.base_url = "https://api-redemet.decea.mil.br"
        self.api_key = settings.REDEMET_API_KEY if hasattr(settings, 'REDEMET_API_KEY') else ""
        self.session: Optional[aiohttp.ClientSession] = None
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout_duration=30, half_open_max_calls=1)
        self.cache = CacheManager()
        self.backoff = ExponentialBackoff(initial_delay=1.0, max_delay=8.0, multiplier=2.0, jitter=True)
        self.valid_brazilian_icao = {"SBSP", "SBGR", "SBBR", "SBRF", "SBCT", "SBPA", "SBFL", "SBSV", "SBFZ", "SBRE", "SBMO", "SBCF", "SBGO", "SBCY", "SBJP", "SBMQ", "SBSL", "SBVT", "SBIZ", "SBKG", "SBPV", "SBCG", "SBUL", "SBJI", "SBNT", "SBTE", "SBMG", "SBPF", "SBRD", "SBHT", "SBIP", "SBAQ"}
        self.cache_ttl_config = {
            RedemetDataType.AERODROMOS: 86400,
            RedemetDataType.AERODROMOS_STATUS: 1800,
            RedemetDataType.AERODROMOS_INFO: 3600,
            RedemetDataType.METAR: 600,
            RedemetDataType.TAF: 1800,
            RedemetDataType.SIGMET: 300,
            RedemetDataType.GAMET: 300,
            RedemetDataType.PILOT: 900,
            RedemetDataType.TEMP: 900,
            RedemetDataType.AVISO: 300,
            RedemetDataType.METEOGRAMA: 1800,
            RedemetDataType.AMDAR: 900,
            RedemetDataType.MODELO: 3600,
            RedemetDataType.RADAR: 1800,
            RedemetDataType.SATELITE: 1800,
            RedemetDataType.SIGWX: 3600,
            RedemetDataType.STSC: 3600
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15), headers={"User-Agent": "Stratus.IA/1.0", "Accept": "application/json"})
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def validate_icao_code(self, icao_code: str) -> tuple[bool, Optional[str]]:
        if not icao_code or len(icao_code) != 4:
            return False, "Código ICAO deve ter exatamente 4 letras"
        icao_upper = icao_code.upper()
        if not re.match(r'^[A-Z]{4}$', icao_upper):
            return False, "Código ICAO deve conter apenas letras"
        if not icao_upper.startswith('SB'):
            return False, "Códigos ICAO brasileiros começam com 'SB'"
        if icao_upper not in self.valid_brazilian_icao:
            similar = [code for code in self.valid_brazilian_icao if code[:3] == icao_upper[:3] or code[2:] == icao_upper[2:]]
            suggestion = f". Códigos similares: {', '.join(similar[:3])}" if similar else ""
            return False, f"Código ICAO {icao_upper} não encontrado{suggestion}"
        return True, None

    def _generate_cache_key(self, data_type: RedemetDataType, **params) -> str:
        key_data = {"type": data_type.value, **params}
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_cache_ttl(self, data_type: RedemetDataType) -> int:
        return self.cache_ttl_config.get(data_type, 600)

    async def get_aerodromos(self, pais: str = "BR", user_id: str = "system") -> RedemetResponse:
        cache_key = self._generate_cache_key(RedemetDataType.AERODROMOS, pais=pais)
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            params = {"pais": pais}
            response_data = await self._make_request("aerodromos/", params, RedemetDataType.AERODROMOS)
            processed_data = {
                "total_aerodromos": len(response_data.get("data", [])),
                "aerodromos": response_data.get("data", []),
                "pais": pais
            }
            result = RedemetResponse(
                data_type=RedemetDataType.AERODROMOS,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.AERODROMOS)
            await self.cache.set(cache_key, asdict(result), ttl)
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_aerodromos",
                message=f"Lista de aeródromos obtida para {pais}: {processed_data['total_aerodromos']} aeródromos",
                user_id=user_id,
                success=True
            )
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_aerodromos",
                message=f"Erro ao obter aeródromos para {pais}: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

    async def get_aerodromos_status(self, pais: str = "BR", localidades: str = None, user_id: str = "system") -> RedemetResponse:
        cache_key = self._generate_cache_key(RedemetDataType.AERODROMOS_STATUS, pais=pais, localidades=localidades)
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            params = {"pais": pais}
            if localidades:
                params["localidades"] = localidades
            response_data = await self._make_request("aerodromos/status", params, RedemetDataType.AERODROMOS_STATUS)
            processed_data = {
                "status_info": response_data.get("data", []),
                "pais": pais,
                "localidades_consultadas": localidades
            }
            result = RedemetResponse(
                data_type=RedemetDataType.AERODROMOS_STATUS,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.AERODROMOS_STATUS)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_aerodromos_status",
                message=f"Erro ao obter status de aeródromos: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

    async def get_aerodromos_info(self, localidade: str, metar: bool = True, taf: bool = True, datahora: str = None, user_id: str = "system") -> RedemetResponse:
        is_valid, error_msg = self.validate_icao_code(localidade)
        if not is_valid:
            raise ValueError(f"Código ICAO inválido: {error_msg}")
        localidade_upper = localidade.upper()
        cache_key = self._generate_cache_key(
            RedemetDataType.AERODROMOS_INFO, 
            localidade=localidade_upper, 
            metar=metar, 
            taf=taf, 
            datahora=datahora
        )
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            params = {"localidade": localidade_upper}
            if metar:
                params["metar"] = "true"
            if taf:
                params["taf"] = "true"
            if datahora:
                params["datahora"] = datahora
            response_data = await self._make_request("aerodromos/info", params, RedemetDataType.AERODROMOS_INFO)
            data_info = response_data.get("data", {})
            processed_data = {
                "aerodrome_info": data_info.get("info", {}),
                "metar_data": data_info.get("metar", []) if metar else None,
                "taf_data": data_info.get("taf", []) if taf else None,
                "localidade": localidade_upper,
                "consulta_timestamp": datetime.now(timezone.utc).isoformat()
            }
            result = RedemetResponse(
                data_type=RedemetDataType.AERODROMOS_INFO,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.AERODROMOS_INFO)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_aerodromos_info",
                message=f"Erro ao obter informações do aeródromo {localidade_upper}: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

    async def get_mensagens_metar(self, localidades: str, user_id: str = "system") -> RedemetResponse:
        icao_codes = [code.strip().upper() for code in localidades.split(",")]
        for icao_code in icao_codes:
            is_valid, error_msg = self.validate_icao_code(icao_code)
            if not is_valid:
                raise ValueError(f"Código ICAO inválido '{icao_code}': {error_msg}")
        localidades_clean = ",".join(icao_codes)
        cache_key = self._generate_cache_key(RedemetDataType.METAR, localidades=localidades_clean)
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            endpoint = f"mensagens/metar/{quote(localidades_clean)}"
            response_data = await self._make_request(endpoint, {}, RedemetDataType.METAR)
            metar_messages = response_data.get("data", [])
            processed_data = {
                "metar_count": len(metar_messages),
                "localidades": icao_codes,
                "metar_messages": metar_messages,
                "observation_times": [msg.get("validade") for msg in metar_messages if msg.get("validade")]
            }
            result = RedemetResponse(
                data_type=RedemetDataType.METAR,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.METAR)
            await self.cache.set(cache_key, asdict(result), ttl)
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_mensagens_metar",
                message=f"METAR obtido para {len(icao_codes)} localidades: {localidades_clean}",
                user_id=user_id,
                success=True,
                additional_context={"icao_codes": icao_codes}
            )
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_mensagens_metar",
                message=f"Erro ao obter METAR para {localidades_clean}: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

    async def get_mensagens_taf(self, localidades: str, user_id: str = "system") -> RedemetResponse:
        icao_codes = [code.strip().upper() for code in localidades.split(",")]
        for icao_code in icao_codes:
            is_valid, error_msg = self.validate_icao_code(icao_code)
            if not is_valid:
                raise ValueError(f"Código ICAO inválido '{icao_code}': {error_msg}")
        localidades_clean = ",".join(icao_codes)
        cache_key = self._generate_cache_key(RedemetDataType.TAF, localidades=localidades_clean)
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            params = {"localidades": localidades_clean}
            response_data = await self._make_request("mensagens/taf", params, RedemetDataType.TAF)
            taf_messages = response_data.get("data", [])
            processed_data = {
                "taf_count": len(taf_messages),
                "localidades": icao_codes,
                "taf_messages": taf_messages,
                "forecast_periods": [msg.get("validade") for msg in taf_messages if msg.get("validade")]
            }
            result = RedemetResponse(
                data_type=RedemetDataType.TAF,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.TAF)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_mensagens_taf",
                message=f"Erro ao obter TAF para {localidades_clean}: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

    async def get_mensagens_sigmet(self, user_id: str = "system") -> RedemetResponse:
        cache_key = self._generate_cache_key(RedemetDataType.SIGMET)
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            response_data = await self._make_request("mensagens/sigmet", {}, RedemetDataType.SIGMET)
            sigmet_messages = response_data.get("data", [])
            processed_data = {
                "sigmet_count": len(sigmet_messages),
                "sigmet_messages": sigmet_messages,
                "active_sigmets": [msg for msg in sigmet_messages if msg.get("ativo", False)]
            }
            result = RedemetResponse(
                data_type=RedemetDataType.SIGMET,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.SIGMET)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_safety_violation(
                violation_type="SIGMET_ACCESS_FAILURE",
                message=f"Falha crítica ao acessar dados SIGMET: {str(e)}",
                agent_name="RedemetMCPServer",
                user_id=user_id,
                severity="HIGH"
            )
            raise

    async def get_mensagens_gamet(self, user_id: str = "system") -> RedemetResponse:
        cache_key = self._generate_cache_key(RedemetDataType.GAMET)
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            response_data = await self._make_request("mensagens/gamet", {}, RedemetDataType.GAMET)
            gamet_messages = response_data.get("data", [])
            processed_data = {
                "gamet_count": len(gamet_messages),
                "gamet_messages": gamet_messages
            }
            result = RedemetResponse(
                data_type=RedemetDataType.GAMET,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.GAMET)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_mensagens_gamet",
                message=f"Erro ao obter GAMET: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

    async def get_mensagens_pilot(self, user_id: str = "system") -> RedemetResponse:
        cache_key = self._generate_cache_key(RedemetDataType.PILOT)
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            response_data = await self._make_request("mensagens/pilot", {}, RedemetDataType.PILOT)
            pilot_reports = response_data.get("data", [])
            processed_data = {
                "pilot_report_count": len(pilot_reports),
                "pilot_reports": pilot_reports
            }
            result = RedemetResponse(
                data_type=RedemetDataType.PILOT,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.PILOT)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_mensagens_pilot",
                message=f"Erro ao obter relatórios PILOT: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

    async def get_mensagens_temp(self, user_id: str = "system") -> RedemetResponse:
        cache_key = self._generate_cache_key(RedemetDataType.TEMP)
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            response_data = await self._make_request("mensagens/temp", {}, RedemetDataType.TEMP)
            temp_messages = response_data.get("data", [])
            processed_data = {
                "temp_message_count": len(temp_messages),
                "temp_messages": temp_messages
            }
            result = RedemetResponse(
                data_type=RedemetDataType.TEMP,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.TEMP)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_mensagens_temp",
                message=f"Erro ao obter mensagens TEMP: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

    async def get_mensagens_aviso(self, localidades: str, data_ini: str, data_fim: str, user_id: str = "system") -> RedemetResponse:
        icao_codes = [code.strip().upper() for code in localidades.split(",")]
        for icao_code in icao_codes:
            is_valid, error_msg = self.validate_icao_code(icao_code)
            if not is_valid:
                raise ValueError(f"Código ICAO inválido '{icao_code}': {error_msg}")
        localidades_clean = ",".join(icao_codes)
        cache_key = self._generate_cache_key(
            RedemetDataType.AVISO, 
            localidades=localidades_clean, 
            data_ini=data_ini, 
            data_fim=data_fim
        )
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            endpoint = f"mensagens/aviso/{quote(localidades_clean)}"
            params = {
                "data_ini": data_ini,
                "data_fim": data_fim
            }
            response_data = await self._make_request(endpoint, params, RedemetDataType.AVISO)
            warning_messages = response_data.get("data", [])
            processed_data = {
                "warning_count": len(warning_messages),
                "localidades": icao_codes,
                "data_periodo": {"inicio": data_ini, "fim": data_fim},
                "avisos": warning_messages,
                "avisos_ativos": [msg for msg in warning_messages if msg.get("ativo", False)]
            }
            result = RedemetResponse(
                data_type=RedemetDataType.AVISO,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.AVISO)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_safety_violation(
                violation_type="WARNING_ACCESS_FAILURE",
                message=f"Falha ao acessar avisos meteorológicos: {str(e)}",
                agent_name="RedemetMCPServer",
                user_id=user_id,
                severity="HIGH"
            )
            raise

    async def get_mensagens_meteograma(self, localidade: str, user_id: str = "system") -> RedemetResponse:
        is_valid, error_msg = self.validate_icao_code(localidade)
        if not is_valid:
            raise ValueError(f"Código ICAO inválido: {error_msg}")
        localidade_upper = localidade.upper()
        cache_key = self._generate_cache_key(RedemetDataType.METEOGRAMA, localidade=localidade_upper)
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            endpoint = f"mensagens/meteograma/{quote(localidade_upper)}"
            response_data = await self._make_request(endpoint, {}, RedemetDataType.METEOGRAMA)
            meteogram_data = response_data.get("data", {})
            processed_data = {
                "localidade": localidade_upper,
                "meteogram_data": meteogram_data,
                "forecast_hours": meteogram_data.get("horas", []) if isinstance(meteogram_data, dict) else []
            }
            result = RedemetResponse(
                data_type=RedemetDataType.METEOGRAMA,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.METEOGRAMA)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_mensagens_meteograma",
                message=f"Erro ao obter meteograma para {localidade_upper}: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

    async def get_produtos_amdar(self, data: str = None, user_id: str = "system") -> RedemetResponse:
        cache_key = self._generate_cache_key(RedemetDataType.AMDAR, data=data)
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            params = {}
            if data:
                params["data"] = data
            response_data = await self._make_request("produtos/amdar", params, RedemetDataType.AMDAR)
            amdar_data = response_data.get("data", [])
            processed_data = {
                "amdar_count": len(amdar_data),
                "data_consulta": data,
                "amdar_reports": amdar_data
            }
            result = RedemetResponse(
                data_type=RedemetDataType.AMDAR,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.AMDAR)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_produtos_amdar",
                message=f"Erro ao obter produtos AMDAR: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

    async def get_produtos_modelo(self, modelo: str, area: str, produto: str, nivel: str, anima: bool = False, user_id: str = "system") -> RedemetResponse:
        cache_key = self._generate_cache_key(
            RedemetDataType.MODELO, 
            modelo=modelo, 
            area=area, 
            produto=produto, 
            nivel=nivel, 
            anima=anima
        )
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            params = {
                "modelo": modelo,
                "area": area,
                "produto": produto,
                "nivel": nivel
            }
            if anima:
                params["anima"] = "true"
            response_data = await self._make_request("produtos/modelo", params, RedemetDataType.MODELO)
            model_data = response_data.get("data", {})
            processed_data = {
                "modelo": modelo,
                "area": area,
                "produto": produto,
                "nivel": nivel,
                "animacao": anima,
                "model_data": model_data
            }
            result = RedemetResponse(
                data_type=RedemetDataType.MODELO,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.MODELO)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_produtos_modelo",
                message=f"Erro ao obter modelo {modelo}: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

    async def get_produtos_radar(self, tipo: str, area: str, data: str = None, anima: bool = False, user_id: str = "system") -> RedemetResponse:
        cache_key = self._generate_cache_key(
            RedemetDataType.RADAR, 
            tipo=tipo, 
            area=area, 
            data=data, 
            anima=anima
        )
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            endpoint = f"produtos/radar/{quote(tipo)}"
            params = {"area": area}
            if data:
                params["data"] = data
            if anima:
                params["anima"] = "true"
            response_data = await self._make_request(endpoint, params, RedemetDataType.RADAR)
            radar_data = response_data.get("data", {})
            processed_data = {
                "tipo": tipo,
                "area": area,
                "data": data,
                "animacao": anima,
                "radar_data": radar_data
            }
            result = RedemetResponse(
                data_type=RedemetDataType.RADAR,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.RADAR)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_produtos_radar",
                message=f"Erro ao obter radar {tipo}: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

    async def get_produtos_satelite(self, tipo: str, data: str = None, anima: bool = False, user_id: str = "system") -> RedemetResponse:
        cache_key = self._generate_cache_key(
            RedemetDataType.SATELITE, 
            tipo=tipo, 
            data=data, 
            anima=anima
        )
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            endpoint = f"produtos/satelite/{quote(tipo)}"
            params = {}
            if data:
                params["data"] = data
            if anima:
                params["anima"] = "true"
            response_data = await self._make_request(endpoint, params, RedemetDataType.SATELITE)
            satellite_data = response_data.get("data", {})
            processed_data = {
                "tipo": tipo,
                "data": data,
                "animacao": anima,
                "satellite_data": satellite_data
            }
            result = RedemetResponse(
                data_type=RedemetDataType.SATELITE,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.SATELITE)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_produtos_satelite",
                message=f"Erro ao obter satélite {tipo}: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

    async def get_produtos_sigwx(self, user_id: str = "system") -> RedemetResponse:
        cache_key = self._generate_cache_key(RedemetDataType.SIGWX)
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            response_data = await self._make_request("produtos/sigwx", {}, RedemetDataType.SIGWX)
            sigwx_data = response_data.get("data", {})
            processed_data = {
                "sigwx_data": sigwx_data
            }
            result = RedemetResponse(
                data_type=RedemetDataType.SIGWX,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.SIGWX)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_produtos_sigwx",
                message=f"Erro ao obter produtos SIGWX: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

    async def get_produtos_stsc(self, user_id: str = "system") -> RedemetResponse:
        cache_key = self._generate_cache_key(RedemetDataType.STSC)
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return RedemetResponse(**cached_data, cache_hit=True)
        try:
            response_data = await self._make_request("produtos/stsc", {}, RedemetDataType.STSC)
            stsc_data = response_data.get("data", {})
            processed_data = {
                "stsc_data": stsc_data
            }
            result = RedemetResponse(
                data_type=RedemetDataType.STSC,
                raw_data=response_data,
                processed_data=processed_data
            )
            ttl = self._get_cache_ttl(RedemetDataType.STSC)
            await self.cache.set(cache_key, asdict(result), ttl)
            return result
        except Exception as e:
            logger.log_agent_action(
                agent_name="RedemetMCPServer",
                action="get_produtos_stsc",
                message=f"Erro ao obter produtos STSC: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

# ==================== MCP TOOLS INTERFACE ====================

# GRUPO 1: AERÓDROMOS
async def get_aerodromos_tool(pais: str = "BR", user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_aerodromos(pais, user_id)
        return asdict(result)

async def get_aerodromos_status_tool(pais: str = "BR", localidades: str = None, user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_aerodromos_status(pais, localidades, user_id)
        return asdict(result)

async def get_aerodromos_info_tool(localidade: str, metar: bool = True, taf: bool = True, datahora: str = None, user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_aerodromos_info(localidade, metar, taf, datahora, user_id)
        return asdict(result)

# GRUPO 2: MENSAGENS METEOROLÓGICAS
async def get_mensagens_metar_tool(localidades: str, user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_mensagens_metar(localidades, user_id)
        return asdict(result)

async def get_mensagens_taf_tool(localidades: str, user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_mensagens_taf(localidades, user_id)
        return asdict(result)

async def get_mensagens_sigmet_tool(user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_mensagens_sigmet(user_id)
        return asdict(result)

async def get_mensagens_gamet_tool(user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_mensagens_gamet(user_id)
        return asdict(result)

async def get_mensagens_pilot_tool(user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_mensagens_pilot(user_id)
        return asdict(result)

async def get_mensagens_temp_tool(user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_mensagens_temp(user_id)
        return asdict(result)

async def get_mensagens_aviso_tool(localidades: str, data_ini: str, data_fim: str, user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_mensagens_aviso(localidades, data_ini, data_fim, user_id)
        return asdict(result)

async def get_mensagens_meteograma_tool(localidade: str, user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_mensagens_meteograma(localidade, user_id)
        return asdict(result)

# GRUPO 3: PRODUTOS METEOROLÓGICOS
async def get_produtos_amdar_tool(data: str = None, user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_produtos_amdar(data, user_id)
        return asdict(result)

async def get_produtos_modelo_tool(modelo: str, area: str, produto: str, nivel: str, anima: bool = False, user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_produtos_modelo(modelo, area, produto, nivel, anima, user_id)
        return asdict(result)

async def get_produtos_radar_tool(tipo: str, area: str, data: str = None, anima: bool = False, user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_produtos_radar(tipo, area, data, anima, user_id)
        return asdict(result)

async def get_produtos_satelite_tool(tipo: str, data: str = None, anima: bool = False, user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_produtos_satelite(tipo, data, anima, user_id)
        return asdict(result)

async def get_produtos_sigwx_tool(user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_produtos_sigwx(user_id)
        return asdict(result)

async def get_produtos_stsc_tool(user_id: str = "system") -> Dict[str, Any]:
    async with RedemetMCPServer() as server:
        result = await server.get_produtos_stsc(user_id)
        return asdict(result)

# Export ALL 17 MCP tools
MCP_TOOLS = {
    # GRUPO 1: AERÓDROMOS
    "get_aerodromos": get_aerodromos_tool,
    "get_aerodromos_status": get_aerodromos_status_tool,
    "get_aerodromos_info": get_aerodromos_info_tool,
    # GRUPO 2: MENSAGENS METEOROLÓGICAS
    "get_mensagens_metar": get_mensagens_metar_tool,
    "get_mensagens_taf": get_mensagens_taf_tool,
    "get_mensagens_sigmet": get_mensagens_sigmet_tool,
    "get_mensagens_gamet": get_mensagens_gamet_tool,
    "get_mensagens_pilot": get_mensagens_pilot_tool,
    "get_mensagens_temp": get_mensagens_temp_tool,
    "get_mensagens_aviso": get_mensagens_aviso_tool,
    "get_mensagens_meteograma": get_mensagens_meteograma_tool,
    # GRUPO 3: PRODUTOS METEOROLÓGICOS
    "get_produtos_amdar": get_produtos_amdar_tool,
    "get_produtos_modelo": get_produtos_modelo_tool,
    "get_produtos_radar": get_produtos_radar_tool,
    "get_produtos_satelite": get_produtos_satelite_tool,
    "get_produtos_sigwx": get_produtos_sigwx_tool,
    "get_produtos_stsc": get_produtos_stsc_tool
} 