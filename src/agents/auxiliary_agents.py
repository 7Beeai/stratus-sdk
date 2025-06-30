import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from abc import ABC, abstractmethod

from src.utils.logging import get_logger
from src.config.settings import get_settings
from src.mcp_servers import redemet_server, pinecone_server, aisweb_server, airportdb_server, weather_apis_server, anac_regulations_server
from src.agents.handoffs import handoff_manager, AgentEnum

logger = get_logger()
settings = get_settings()

@dataclass
class AgentRequest:
    """Solicitação para agente auxiliar"""
    query: str
    context: Dict[str, Any]
    user_id: str
    urgency: str
    entities: Dict[str, List[str]]
    timestamp: datetime

@dataclass
class AgentResponse:
    """Resposta de agente auxiliar"""
    agent_name: str
    content: str
    sources: List[str]
    confidence: float
    reasoning: str
    success: bool
    timestamp: datetime
    error_message: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None

class BaseAuxiliaryAgent(ABC):
    """Classe base para todos os agentes auxiliares"""
    def __init__(self, agent_name: str, specialization: str):
        self.agent_name = agent_name
        self.specialization = specialization
        self.logger = get_logger()
        handoff_manager.register_agent(AgentEnum.<NOME>, self)

    @abstractmethod
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        pass

    def _log_action(self, action: str, message: str, success: bool, additional_context: Dict[str, Any] = None):
        self.logger.log_agent_action(
            agent_name=self.agent_name,
            action=action,
            message=message,
            user_id=additional_context.get('user_id', 'system') if additional_context else 'system',
            success=success,
            additional_context=additional_context or {}
        )

    def _format_sources(self, sources: List[str]) -> List[str]:
        formatted_sources = []
        for source in sources:
            if source and source.strip():
                if 'consultado em' not in source.lower():
                    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M UTC')
                    source = f"{source} (consultado em {timestamp})"
                formatted_sources.append(source)
        return formatted_sources

# =============================
# 1. REGULATORY AGENT
# =============================
class RegulatoryAgent(BaseAuxiliaryAgent):
    """
    Agente Auxiliar 1 - Regulamentação Aeronáutica
    Especializado em RBACs, ISs, ANAC, ICAO
    """
    def __init__(self):
        super().__init__("RegulatoryAgent", "Regulamentação Aeronáutica")
        self.priority_sources = ["RBAC", "IS", "ANAC", "ICAO", "DECEA"]
        handoff_manager.register_agent(AgentEnum.REGULATORY, self)

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        self._log_action(
            "process_regulatory_request",
            f"Processando consulta regulatória: {request.query[:100]}...",
            True,
            {"user_id": request.user_id, "urgency": request.urgency}
        )
        try:
            regulation_type = self._identify_regulation_type(request.query)
            search_terms = self._extract_regulatory_terms(request.query, request.entities)
            sources_data = await self._query_regulatory_sources(search_terms, regulation_type)
            validated_info = self._validate_regulatory_info(sources_data)
            response_content = self._build_regulatory_response(validated_info, regulation_type)
            formatted_response = self._format_regulatory_output(response_content, validated_info)
            return AgentResponse(
                agent_name=self.agent_name,
                content=formatted_response,
                sources=self._format_sources(validated_info.get('sources', [])),
                confidence=validated_info.get('confidence', 0.8),
                reasoning=f"Consulta regulatória sobre {regulation_type} processada com {len(sources_data)} fontes",
                success=True,
                timestamp=datetime.now(timezone.utc),
                additional_data={
                    "regulation_type": regulation_type,
                    "search_terms": search_terms,
                    "sources_count": len(sources_data)
                }
            )
        except Exception as e:
            self._log_action(
                "regulatory_error",
                f"Erro no processamento regulatório: {str(e)}",
                False,
                {"user_id": request.user_id, "error": str(e)}
            )
            return AgentResponse(
                agent_name=self.agent_name,
                content="⚠ Informação regulatória não disponível nas fontes oficiais consultadas. Recomenda-se consultar diretamente o Portal ANAC ou documentação oficial.",
                sources=[],
                confidence=0.0,
                reasoning=f"Erro no processamento: {str(e)}",
                success=False,
                timestamp=datetime.now(timezone.utc),
                error_message=str(e)
            )

    def _identify_regulation_type(self, query: str) -> str:
        query_lower = query.lower()
        if any(term in query_lower for term in ['rbac', 'regulamento brasileiro']):
            return "RBAC"
        elif any(term in query_lower for term in ['is', 'instrução suplementar']):
            return "IS"
        elif any(term in query_lower for term in ['icao', 'anexo', 'doc']):
            return "ICAO"
        elif any(term in query_lower for term in ['ica', 'instrução']):
            return "ICA"
        elif any(term in query_lower for term in ['licença', 'habilitação', 'certificado']):
            return "Licenciamento"
        else:
            return "Geral"

    def _extract_regulatory_terms(self, query: str, entities: Dict[str, List[str]]) -> List[str]:
        terms = []
        if 'regulations' in entities:
            terms.extend(entities['regulations'])
        import re
        rbac_matches = re.findall(r'rbac[-\s]?(\d+)', query.lower())
        is_matches = re.findall(r'is[-\s]?(\d+)', query.lower())
        terms.extend([f"RBAC {num}" for num in rbac_matches])
        terms.extend([f"IS {num}" for num in is_matches])
        regulatory_keywords = [
            'licença', 'habilitação', 'certificado', 'autorização', 'homologação',
            'requisitos', 'limitações', 'procedimentos', 'normas', 'regulamento'
        ]
        for keyword in regulatory_keywords:
            if keyword in query.lower():
                terms.append(keyword)
        return list(set(terms))

    async def _query_regulatory_sources(self, search_terms: List[str], regulation_type: str) -> List[Dict[str, Any]]:
        sources_data = []
        try:
            for namespace in ['ANAC', 'DECEA', 'ICAO e seus Anexos']:
                for term in search_terms:
                    try:
                        result = await pinecone_server.search_knowledge(
                            query=f"{regulation_type} {term}",
                            namespace=namespace,
                            top_k=3
                        )
                        if result.get('success') and result.get('matches'):
                            sources_data.extend(result['matches'])
                    except Exception as e:
                        self._log_action(
                            "pinecone_query_error",
                            f"Erro na consulta Pinecone {namespace}: {str(e)}",
                            False
                        )
            try:
                for term in search_terms:
                    result = await anac_regulations_server.search_rbac(term)
                    if result.get('success'):
                        sources_data.append({
                            'content': result.get('content', ''),
                            'source': f"ANAC Regulations - {term}",
                            'score': 0.9
                        })
            except Exception as e:
                self._log_action(
                    "anac_regulations_error",
                    f"Erro na consulta ANAC Regulations: {str(e)}",
                    False
                )
        except Exception as e:
            self._log_action(
                "regulatory_sources_error",
                f"Erro geral na consulta de fontes regulatórias: {str(e)}",
                False
            )
        return sources_data

    def _validate_regulatory_info(self, sources_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not sources_data:
            return {
                'content': '',
                'sources': [],
                'confidence': 0.0,
                'validation_status': 'no_data'
            }
        relevant_sources = [s for s in sources_data if s.get('score', 0) > 0.7]
        if not relevant_sources:
            relevant_sources = sources_data[:3]
        consolidated_content = []
        sources_list = []
        for source in relevant_sources:
            content = source.get('content', '').strip()
            source_name = source.get('source', 'Fonte não identificada')
            if content and len(content) > 50:
                consolidated_content.append(content)
                sources_list.append(source_name)
        confidence = min(0.9, len(relevant_sources) * 0.3)
        return {
            'content': '\n\n'.join(consolidated_content),
            'sources': sources_list,
            'confidence': confidence,
            'validation_status': 'validated' if consolidated_content else 'insufficient_data'
        }

    def _build_regulatory_response(self, validated_info: Dict[str, Any], regulation_type: str) -> str:
        if validated_info['validation_status'] == 'no_data':
            return "⚠ Nenhuma informação regulatória encontrada nas fontes consultadas."
        if validated_info['validation_status'] == 'insufficient_data':
            return "⚠ Informação regulatória insuficiente nas fontes oficiais consultadas."
        content = validated_info['content']
        response = f"**REGULAMENTAÇÃO - {regulation_type.upper()}**\n\n"
        response += content
        return response

    def _format_regulatory_output(self, response_content: str, validated_info: Dict[str, Any]) -> str:
        formatted_response = response_content
        if validated_info['confidence'] < 0.8:
            formatted_response += "\n\n⚠ **ATENÇÃO**: Informação com confiança limitada. Confirme com fonte oficial."
        return formatted_response

# =============================
# 2. WEATHER AGENT
# =============================
class WeatherAgent(BaseAuxiliaryAgent):
    """
    Agente Auxiliar 2 - Meteorologia e Informações Operacionais
    Especializado em METAR, TAF, SIGMET, NOTAMs
    """
    def __init__(self):
        super().__init__("WeatherAgent", "Meteorologia e Informações Operacionais")
        self.weather_mcps = [redemet_server, aisweb_server, weather_apis_server]
        handoff_manager.register_agent(AgentEnum.WEATHER, self)

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        self._log_action(
            "process_weather_request",
            f"Processando consulta meteorológica: {request.query[:100]}...",
            True,
            {"user_id": request.user_id, "urgency": request.urgency}
        )
        try:
            weather_type = self._identify_weather_type(request.query)
            icao_codes = request.entities.get('icao_codes', [])
            weather_terms = request.entities.get('weather_terms', [])
            weather_data = await self._query_weather_sources(weather_type, icao_codes, weather_terms)
            interpreted_data = self._interpret_weather_data(weather_data, weather_type)
            response_content = self._build_weather_response(interpreted_data, weather_type)
            return AgentResponse(
                agent_name=self.agent_name,
                content=response_content,
                sources=self._format_sources(interpreted_data.get('sources', [])),
                confidence=interpreted_data.get('confidence', 0.8),
                reasoning=f"Consulta meteorológica {weather_type} para {len(icao_codes)} aeródromos",
                success=True,
                timestamp=datetime.now(timezone.utc),
                additional_data={
                    "weather_type": weather_type,
                    "icao_codes": icao_codes,
                    "weather_terms": weather_terms
                }
            )
        except Exception as e:
            return AgentResponse(
                agent_name=self.agent_name,
                content="⚠ Informação meteorológica não disponível nas fontes oficiais consultadas. Recomenda-se consultar REDEMET ou AISWEB diretamente.",
                sources=[],
                confidence=0.0,
                reasoning=f"Erro no processamento: {str(e)}",
                success=False,
                timestamp=datetime.now(timezone.utc),
                error_message=str(e)
            )

    def _identify_weather_type(self, query: str) -> str:
        query_lower = query.lower()
        if 'metar' in query_lower:
            return "METAR"
        elif 'taf' in query_lower:
            return "TAF"
        elif 'sigmet' in query_lower:
            return "SIGMET"
        elif any(term in query_lower for term in ['tempo', 'condições', 'meteorologia']):
            return "GERAL"
        elif 'notam' in query_lower:
            return "NOTAM"
        else:
            return "GERAL"

    async def _query_weather_sources(self, weather_type: str, icao_codes: List[str], weather_terms: List[str]) -> List[Dict[str, Any]]:
        weather_data = []
        for icao in icao_codes:
            try:
                if weather_type in ["METAR", "GERAL"]:
                    result = await redemet_server.get_mensagens_metar(icao)
                    if result.get('success'):
                        weather_data.append({
                            'type': 'METAR',
                            'icao': icao,
                            'data': result.get('data'),
                            'source': 'REDEMET'
                        })
                if weather_type in ["TAF", "GERAL"]:
                    result = await redemet_server.get_mensagens_taf(icao)
                    if result.get('success'):
                        weather_data.append({
                            'type': 'TAF',
                            'icao': icao,
                            'data': result.get('data'),
                            'source': 'REDEMET'
                        })
            except Exception as e:
                self._log_action(
                    "redemet_query_error",
                    f"Erro na consulta REDEMET para {icao}: {str(e)}",
                    False
                )
        return weather_data

    def _interpret_weather_data(self, weather_data: List[Dict[str, Any]], weather_type: str) -> Dict[str, Any]:
        if not weather_data:
            return {
                'content': '',
                'sources': [],
                'confidence': 0.0,
                'interpretation': 'no_data'
            }
        interpreted_content = []
        sources_list = []
        for data in weather_data:
            data_type = data.get('type', '')
            icao = data.get('icao', '')
            raw_data = data.get('data', {})
            source = data.get('source', '')
            if raw_data:
                interpreted_content.append(f"**{data_type} {icao}:**\n{self._format_weather_data(raw_data, data_type)}")
                sources_list.append(f"{source} - {data_type} {icao}")
        confidence = min(0.9, len(weather_data) * 0.4)
        return {
            'content': '\n\n'.join(interpreted_content),
            'sources': sources_list,
            'confidence': confidence,
            'interpretation': 'success' if interpreted_content else 'no_valid_data'
        }

    def _format_weather_data(self, raw_data: Dict[str, Any], data_type: str) -> str:
        if data_type == "METAR":
            return self._format_metar(raw_data)
        elif data_type == "TAF":
            return self._format_taf(raw_data)
        else:
            return str(raw_data)

    def _format_metar(self, metar_data: Dict[str, Any]) -> str:
        formatted = []
        if 'raw' in metar_data:
            formatted.append(f"Código: {metar_data['raw']}")
        if 'time' in metar_data:
            formatted.append(f"Horário: {metar_data['time']}")
        if 'wind' in metar_data:
            wind = metar_data['wind']
            formatted.append(f"Vento: {wind.get('direction', 'N/A')}°/{wind.get('speed', 'N/A')}kt")
        if 'visibility' in metar_data:
            formatted.append(f"Visibilidade: {metar_data['visibility']}")
        return '\n'.join(formatted) if formatted else str(metar_data)

    def _format_taf(self, taf_data: Dict[str, Any]) -> str:
        formatted = []
        if 'raw' in taf_data:
            formatted.append(f"Código: {taf_data['raw']}")
        if 'valid_from' in taf_data and 'valid_to' in taf_data:
            formatted.append(f"Válido: {taf_data['valid_from']} até {taf_data['valid_to']}")
        return '\n'.join(formatted) if formatted else str(taf_data)

    def _build_weather_response(self, interpreted_data: Dict[str, Any], weather_type: str) -> str:
        if interpreted_data['interpretation'] == 'no_data':
            return "⚠ Nenhuma informação meteorológica encontrada nas fontes consultadas."
        if interpreted_data['interpretation'] == 'no_valid_data':
            return "⚠ Dados meteorológicos indisponíveis ou inválidos nas fontes consultadas."
        content = interpreted_data['content']
        response = f"**METEOROLOGIA - {weather_type.upper()}**\n\n{content}"
        return response

# =============================
# 3. PERFORMANCE AGENT
# =============================
class PerformanceAgent(BaseAuxiliaryAgent):
    """
    Agente Auxiliar 3 - Peso, Balanceamento e Performance
    Especializado em cálculos de peso/CG, performance, limitações
    """
    def __init__(self):
        super().__init__("PerformanceAgent", "Peso, Balanceamento e Performance")
        handoff_manager.register_agent(AgentEnum.PERFORMANCE, self)

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        try:
            performance_type = self._identify_performance_type(request.query)
            aircraft_types = request.entities.get('aircraft_types', [])
            performance_data = await self._query_performance_sources(performance_type, aircraft_types)
            calculated_data = self._calculate_performance(performance_data, performance_type)
            response_content = self._build_performance_response(calculated_data, performance_type)
            return AgentResponse(
                agent_name=self.agent_name,
                content=response_content,
                sources=self._format_sources(calculated_data.get('sources', [])),
                confidence=calculated_data.get('confidence', 0.7),
                reasoning=f"Análise de performance {performance_type} para {len(aircraft_types)} aeronaves",
                success=True,
                timestamp=datetime.now(timezone.utc),
                additional_data={
                    "performance_type": performance_type,
                    "aircraft_types": aircraft_types
                }
            )
        except Exception as e:
            return AgentResponse(
                agent_name=self.agent_name,
                content="⚠ Informação de performance não disponível nas fontes oficiais consultadas. Recomenda-se consultar POH/AFM específico da aeronave.",
                sources=[],
                confidence=0.0,
                reasoning=f"Erro no processamento: {str(e)}",
                success=False,
                timestamp=datetime.now(timezone.utc),
                error_message=str(e)
            )

    def _identify_performance_type(self, query: str) -> str:
        query_lower = query.lower()
        if any(term in query_lower for term in ['peso', 'weight', 'cg', 'balanceamento']):
            return "PESO_BALANCEAMENTO"
        elif any(term in query_lower for term in ['decolagem', 'takeoff']):
            return "DECOLAGEM"
        elif any(term in query_lower for term in ['pouso', 'landing']):
            return "POUSO"
        elif any(term in query_lower for term in ['cruzeiro', 'cruise']):
            return "CRUZEIRO"
        elif any(term in query_lower for term in ['combustível', 'fuel']):
            return "COMBUSTIVEL"
        else:
            return "GERAL"

    async def _query_performance_sources(self, performance_type: str, aircraft_types: List[str]) -> List[Dict[str, Any]]:
        performance_data = []
        try:
            for aircraft in aircraft_types:
                result = await pinecone_server.search_knowledge(
                    query=f"{performance_type} {aircraft}",
                    namespace="PesoBalanceamento_Performance",
                    top_k=5
                )
                if result.get('success') and result.get('matches'):
                    performance_data.extend(result['matches'])
        except Exception as e:
            self._log_action(
                "performance_query_error",
                f"Erro na consulta de performance: {str(e)}",
                False
            )
        return performance_data

    def _calculate_performance(self, performance_data: List[Dict[str, Any]], performance_type: str) -> Dict[str, Any]:
        if not performance_data:
            return {
                'content': '',
                'sources': [],
                'confidence': 0.0,
                'calculations': 'no_data'
            }
        relevant_data = [d for d in performance_data if d.get('score', 0) > 0.6]
        if not relevant_data:
            relevant_data = performance_data[:3]
        consolidated_content = []
        sources_list = []
        for data in relevant_data:
            content = data.get('content', '').strip()
            source = data.get('source', 'Fonte não identificada')
            if content:
                consolidated_content.append(content)
                sources_list.append(source)
        confidence = min(0.8, len(relevant_data) * 0.25)
        return {
            'content': '\n\n'.join(consolidated_content),
            'sources': sources_list,
            'confidence': confidence,
            'calculations': 'completed' if consolidated_content else 'insufficient_data'
        }

    def _build_performance_response(self, calculated_data: Dict[str, Any], performance_type: str) -> str:
        if calculated_data['calculations'] == 'no_data':
            return "⚠ Nenhum dado de performance encontrado nas fontes consultadas."
        if calculated_data['calculations'] == 'insufficient_data':
            return "⚠ Dados de performance insuficientes nas fontes consultadas."
        content = calculated_data['content']
        response = f"**PERFORMANCE - {performance_type.upper()}**\n\n{content}"
        return response

# =============================
# 4. TECHNICAL AGENT
# =============================
class TechnicalAgent(BaseAuxiliaryAgent):
    """
    Agente Auxiliar 4 - Aeronaves, Sistemas, Manuais Técnicos
    Especializado em POH/AFM, QRH, MEL, sistemas embarcados
    """
    def __init__(self):
        super().__init__("TechnicalAgent", "Aeronaves, Sistemas, Manuais Técnicos")
        handoff_manager.register_agent(AgentEnum.TECHNICAL, self)

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        try:
            technical_type = self._identify_technical_type(request.query)
            aircraft_types = request.entities.get('aircraft_types', [])
            technical_data = await self._query_technical_sources(technical_type, aircraft_types)
            validated_data = self._validate_technical_data(technical_data, technical_type)
            response_content = self._build_technical_response(validated_data, technical_type)
            return AgentResponse(
                agent_name=self.agent_name,
                content=response_content,
                sources=self._format_sources(validated_data.get('sources', [])),
                confidence=validated_data.get('confidence', 0.7),
                reasoning=f"Consulta técnica {technical_type} para {len(aircraft_types)} aeronaves",
                success=True,
                timestamp=datetime.now(timezone.utc),
                additional_data={
                    "technical_type": technical_type,
                    "aircraft_types": aircraft_types
                }
            )
        except Exception as e:
            return AgentResponse(
                agent_name=self.agent_name,
                content="⚠ Informação técnica não disponível nas fontes oficiais consultadas. Recomenda-se consultar POH/AFM da aeronave específica.",
                sources=[],
                confidence=0.0,
                reasoning=f"Erro no processamento: {str(e)}",
                success=False,
                timestamp=datetime.now(timezone.utc),
                error_message=str(e)
            )

    def _identify_technical_type(self, query: str) -> str:
        query_lower = query.lower()
        if any(term in query_lower for term in ['sistema', 'systems']):
            return "SISTEMAS"
        elif any(term in query_lower for term in ['poh', 'afm', 'manual']):
            return "MANUAIS"
        elif any(term in query_lower for term in ['qrh', 'checklist', 'procedimento']):
            return "PROCEDIMENTOS"
        elif any(term in query_lower for term in ['mel', 'limitação', 'restriction']):
            return "LIMITACOES"
        elif any(term in query_lower for term in ['avionics', 'aviônicos', 'garmin', 'honeywell']):
            return "AVIONICOS"
        else:
            return "GERAL"

    async def _query_technical_sources(self, technical_type: str, aircraft_types: List[str]) -> List[Dict[str, Any]]:
        technical_data = []
        try:
            namespaces = ["Manuais_Aeronaves_Equipamentos", "InstrumentosAvionicosSistemasEletricos"]
            for namespace in namespaces:
                for aircraft in aircraft_types:
                    result = await pinecone_server.search_knowledge(
                        query=f"{technical_type} {aircraft}",
                        namespace=namespace,
                        top_k=5
                    )
                    if result.get('success') and result.get('matches'):
                        technical_data.extend(result['matches'])
        except Exception as e:
            self._log_action(
                "technical_query_error",
                f"Erro na consulta técnica: {str(e)}",
                False
            )
        return technical_data

    def _validate_technical_data(self, technical_data: List[Dict[str, Any]], technical_type: str) -> Dict[str, Any]:
        if not technical_data:
            return {
                'content': '',
                'sources': [],
                'confidence': 0.0,
                'validation': 'no_data'
            }
        relevant_data = [d for d in technical_data if d.get('score', 0) > 0.7]
        if not relevant_data:
            relevant_data = technical_data[:3]
        consolidated_content = []
        sources_list = []
        for data in relevant_data:
            content = data.get('content', '').strip()
            source = data.get('source', 'Manual não identificado')
            if content and len(content) > 30:
                consolidated_content.append(content)
                sources_list.append(source)
        confidence = min(0.85, len(relevant_data) * 0.3)
        return {
            'content': '\n\n'.join(consolidated_content),
            'sources': sources_list,
            'confidence': confidence,
            'validation': 'validated' if consolidated_content else 'insufficient_data'
        }

    def _build_technical_response(self, validated_data: Dict[str, Any], technical_type: str) -> str:
        if validated_data['validation'] == 'no_data':
            return "⚠ Nenhuma informação técnica encontrada nas fontes consultadas."
        if validated_data['validation'] == 'insufficient_data':
            return "⚠ Informação técnica insuficiente nas fontes consultadas."
        content = validated_data['content']
        response = f"**INFORMAÇÕES TÉCNICAS - {technical_type.upper()}**\n\n{content}"
        return response

# =============================
# 5. EDUCATION AGENT
# =============================
class EducationAgent(BaseAuxiliaryAgent):
    """
    Agente Auxiliar 5 - Educação e Carreira Aeronáutica
    Especializado em licenças, habilitações, exames, formação
    """
    def __init__(self):
        super().__init__("EducationAgent", "Educação e Carreira Aeronáutica")
        handoff_manager.register_agent(AgentEnum.EDUCATION, self)

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        try:
            education_type = self._identify_education_type(request.query)
            education_data = await self._query_education_sources(education_type)
            validated_data = self._validate_education_data(education_data, education_type)
            response_content = self._build_education_response(validated_data, education_type)
            return AgentResponse(
                agent_name=self.agent_name,
                content=response_content,
                sources=self._format_sources(validated_data.get('sources', [])),
                confidence=validated_data.get('confidence', 0.8),
                reasoning=f"Consulta educacional sobre {education_type}",
                success=True,
                timestamp=datetime.now(timezone.utc),
                additional_data={
                    "education_type": education_type
                }
            )
        except Exception as e:
            return AgentResponse(
                agent_name=self.agent_name,
                content="⚠ Informação educacional não disponível nas fontes oficiais consultadas. Recomenda-se consultar Portal ANAC ou RBAC 61/65.",
                sources=[],
                confidence=0.0,
                reasoning=f"Erro no processamento: {str(e)}",
                success=False,
                timestamp=datetime.now(timezone.utc),
                error_message=str(e)
            )

    def _identify_education_type(self, query: str) -> str:
        query_lower = query.lower()
        if any(term in query_lower for term in ['licença', 'license']):
            return "LICENCAS"
        elif any(term in query_lower for term in ['habilitação', 'rating']):
            return "HABILITACOES"
        elif any(term in query_lower for term in ['exame', 'prova', 'teste']):
            return "EXAMES"
        elif any(term in query_lower for term in ['curso', 'treinamento', 'formação']):
            return "CURSOS"
        elif any(term in query_lower for term in ['carreira', 'profissão']):
            return "CARREIRA"
        elif any(term in query_lower for term in ['instrutor', 'instructor']):
            return "INSTRUCAO"
        else:
            return "GERAL"

    async def _query_education_sources(self, education_type: str) -> List[Dict[str, Any]]:
        education_data = []
        try:
            namespaces = [
                "MaterialFormacao_BancaANAC_Simulados",
                "InstrutoresDeVoo",
                "Exame SDEA ICAO ANAC"
            ]
            for namespace in namespaces:
                result = await pinecone_server.search_knowledge(
                    query=education_type,
                    namespace=namespace,
                    top_k=5
                )
                if result.get('success') and result.get('matches'):
                    education_data.extend(result['matches'])
        except Exception as e:
            self._log_action(
                "education_query_error",
                f"Erro na consulta educacional: {str(e)}",
                False
            )
        return education_data

    def _validate_education_data(self, education_data: List[Dict[str, Any]], education_type: str) -> Dict[str, Any]:
        if not education_data:
            return {
                'content': '',
                'sources': [],
                'confidence': 0.0,
                'validation': 'no_data'
            }
        relevant_data = [d for d in education_data if d.get('score', 0) > 0.6]
        if not relevant_data:
            relevant_data = education_data[:3]
        consolidated_content = []
        sources_list = []
        for data in relevant_data:
            content = data.get('content', '').strip()
            source = data.get('source', 'Material educacional não identificado')
            if content:
                consolidated_content.append(content)
                sources_list.append(source)
        confidence = min(0.9, len(relevant_data) * 0.3)
        return {
            'content': '\n\n'.join(consolidated_content),
            'sources': sources_list,
            'confidence': confidence,
            'validation': 'validated' if consolidated_content else 'insufficient_data'
        }

    def _build_education_response(self, validated_data: Dict[str, Any], education_type: str) -> str:
        if validated_data['validation'] == 'no_data':
            return "⚠ Nenhuma informação educacional encontrada nas fontes consultadas."
        if validated_data['validation'] == 'insufficient_data':
            return "⚠ Informação educacional insuficiente nas fontes consultadas."
        content = validated_data['content']
        response = f"**EDUCAÇÃO E CARREIRA - {education_type.upper()}**\n\n{content}"
        return response

# =============================
# 6. COMMUNICATION AGENT
# =============================
class CommunicationAgent(BaseAuxiliaryAgent):
    """
    Agente Auxiliar 6 - Comunicação Técnica e Didática
    Especializado em termos técnicos, siglas, jargões, fraseologia
    """
    def __init__(self):
        super().__init__("CommunicationAgent", "Comunicação Técnica e Didática")
        handoff_manager.register_agent(AgentEnum.COMMUNICATION, self)

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        try:
            communication_type = self._identify_communication_type(request.query)
            communication_data = await self._query_communication_sources(communication_type)
            interpreted_data = self._interpret_communication_data(communication_data, communication_type)
            response_content = self._build_communication_response(interpreted_data, communication_type)
            return AgentResponse(
                agent_name=self.agent_name,
                content=response_content,
                sources=self._format_sources(interpreted_data.get('sources', [])),
                confidence=interpreted_data.get('confidence', 0.8),
                reasoning=f"Consulta de comunicação sobre {communication_type}",
                success=True,
                timestamp=datetime.now(timezone.utc),
                additional_data={
                    "communication_type": communication_type
                }
            )
        except Exception as e:
            return AgentResponse(
                agent_name=self.agent_name,
                content="⚠ Informação de comunicação não disponível nas fontes oficiais consultadas. Recomenda-se consultar AIP GEN ou glossários oficiais.",
                sources=[],
                confidence=0.0,
                reasoning=f"Erro no processamento: {str(e)}",
                success=False,
                timestamp=datetime.now(timezone.utc),
                error_message=str(e)
            )

    def _identify_communication_type(self, query: str) -> str:
        query_lower = query.lower()
        if any(term in query_lower for term in ['fraseologia', 'phraseology']):
            return "FRASEOLOGIA"
        elif any(term in query_lower for term in ['sigla', 'abreviação', 'acronym']):
            return "SIGLAS"
        elif any(term in query_lower for term in ['termo', 'definição', 'conceito']):
            return "TERMOS"
        elif any(term in query_lower for term in ['comunicação', 'radiotelefonia']):
            return "COMUNICACAO"
        elif any(term in query_lower for term in ['frequência', 'frequency']):
            return "FREQUENCIAS"
        else:
            return "GERAL"

    async def _query_communication_sources(self, communication_type: str) -> List[Dict[str, Any]]:
        communication_data = []
        try:
            result = await pinecone_server.search_knowledge(
                query=communication_type,
                namespace="ComunicacoesAereas",
                top_k=5
            )
            if result.get('success') and result.get('matches'):
                communication_data.extend(result['matches'])
        except Exception as e:
            self._log_action(
                "communication_query_error",
                f"Erro na consulta de comunicação: {str(e)}",
                False
            )
        return communication_data

    def _interpret_communication_data(self, communication_data: List[Dict[str, Any]], communication_type: str) -> Dict[str, Any]:
        if not communication_data:
            return {
                'content': '',
                'sources': [],
                'confidence': 0.0,
                'interpretation': 'no_data'
            }
        relevant_data = [d for d in communication_data if d.get('score', 0) > 0.6]
        if not relevant_data:
            relevant_data = communication_data[:3]
        consolidated_content = []
        sources_list = []
        for data in relevant_data:
            content = data.get('content', '').strip()
            source = data.get('source', 'Fonte de comunicação não identificada')
            if content:
                consolidated_content.append(content)
                sources_list.append(source)
        confidence = min(0.9, len(relevant_data) * 0.3)
        return {
            'content': '\n\n'.join(consolidated_content),
            'sources': sources_list,
            'confidence': confidence,
            'interpretation': 'success' if consolidated_content else 'insufficient_data'
        }

    def _build_communication_response(self, interpreted_data: Dict[str, Any], communication_type: str) -> str:
        if interpreted_data['interpretation'] == 'no_data':
            return "⚠ Nenhuma informação de comunicação encontrada nas fontes consultadas."
        if interpreted_data['interpretation'] == 'insufficient_data':
            return "⚠ Informação de comunicação insuficiente nas fontes consultadas."
        content = interpreted_data['content']
        response = f"**COMUNICAÇÃO - {communication_type.upper()}**\n\n{content}"
        return response

# =============================
# 7. GEOGRAPHIC AGENT
# =============================
class GeographicAgent(BaseAuxiliaryAgent):
    """
    Agente Auxiliar 7 - Localização e Adaptação Geográfica
    Especializado em FIRs, aeródromos, cartas, contexto geográfico
    """
    def __init__(self):
        super().__init__("GeographicAgent", "Localização e Adaptação Geográfica")
        handoff_manager.register_agent(AgentEnum.GEOGRAPHIC, self)

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        try:
            geographic_type = self._identify_geographic_type(request.query)
            icao_codes = request.entities.get('icao_codes', [])
            geographic_data = await self._query_geographic_sources(geographic_type, icao_codes)
            validated_data = self._validate_geographic_data(geographic_data, geographic_type)
            response_content = self._build_geographic_response(validated_data, geographic_type)
            return AgentResponse(
                agent_name=self.agent_name,
                content=response_content,
                sources=self._format_sources(validated_data.get('sources', [])),
                confidence=validated_data.get('confidence', 0.8),
                reasoning=f"Consulta geográfica {geographic_type} para {len(icao_codes)} localizações",
                success=True,
                timestamp=datetime.now(timezone.utc),
                additional_data={
                    "geographic_type": geographic_type,
                    "icao_codes": icao_codes
                }
            )
        except Exception as e:
            return AgentResponse(
                agent_name=self.agent_name,
                content="⚠ Informação geográfica não disponível nas fontes oficiais consultadas. Recomenda-se consultar AIP Brasil ou cartas aeronáuticas.",
                sources=[],
                confidence=0.0,
                reasoning=f"Erro no processamento: {str(e)}",
                success=False,
                timestamp=datetime.now(timezone.utc),
                error_message=str(e)
            )

    def _identify_geographic_type(self, query: str) -> str:
        query_lower = query.lower()
        if any(term in query_lower for term in ['aeródromo', 'airport']):
            return "AERODROMOS"
        elif any(term in query_lower for term in ['fir', 'região']):
            return "FIR"
        elif any(term in query_lower for term in ['carta', 'chart']):
            return "CARTAS"
        elif any(term in query_lower for term in ['coordenadas', 'posição']):
            return "COORDENADAS"
        elif any(term in query_lower for term in ['notam', 'restrição']):
            return "NOTAM"
        else:
            return "GERAL"

    async def _query_geographic_sources(self, geographic_type: str, icao_codes: List[str]) -> List[Dict[str, Any]]:
        geographic_data = []
        try:
            for icao in icao_codes:
                result = await airportdb_server.get_airport_info(icao)
                if result.get('success'):
                    geographic_data.append({
                        'type': 'AIRPORT_INFO',
                        'icao': icao,
                        'data': result.get('data'),
                        'source': 'AirportDB'
                    })
            result = await pinecone_server.search_knowledge(
                query=f"{geographic_type} {' '.join(icao_codes)}",
                namespace="AIP_Brasil_Map",
                top_k=5
            )
            if result.get('success') and result.get('matches'):
                geographic_data.extend(result['matches'])
            if geographic_type == "NOTAM":
                for icao in icao_codes:
                    result = await aisweb_server.search_notam(icao_code=icao)
                    if result.get('success'):
                        geographic_data.append({
                            'type': 'NOTAM',
                            'icao': icao,
                            'data': result.get('data'),
                            'source': 'AISWEB'
                        })
        except Exception as e:
            self._log_action(
                "geographic_query_error",
                f"Erro na consulta geográfica: {str(e)}",
                False
            )
        return geographic_data

    def _validate_geographic_data(self, geographic_data: List[Dict[str, Any]], geographic_type: str) -> Dict[str, Any]:
        if not geographic_data:
            return {
                'content': '',
                'sources': [],
                'confidence': 0.0,
                'validation': 'no_data'
            }
        consolidated_content = []
        sources_list = []
        for data in geographic_data:
            if isinstance(data, dict):
                if 'content' in data:
                    content = data.get('content', '').strip()
                    source = data.get('source', 'AIP Brasil')
                    if content:
                        consolidated_content.append(content)
                        sources_list.append(source)
                else:
                    data_type = data.get('type', '')
                    icao = data.get('icao', '')
                    raw_data = data.get('data', {})
                    source = data.get('source', '')
                    if raw_data:
                        formatted_data = self._format_geographic_data(raw_data, data_type, icao)
                        if formatted_data:
                            consolidated_content.append(formatted_data)
                            sources_list.append(f"{source} - {icao}")
        confidence = min(0.9, len(consolidated_content) * 0.3)
        return {
            'content': '\n\n'.join(consolidated_content),
            'sources': sources_list,
            'confidence': confidence,
            'validation': 'validated' if consolidated_content else 'insufficient_data'
        }

    def _format_geographic_data(self, raw_data: Dict[str, Any], data_type: str, icao: str) -> str:
        if data_type == "AIRPORT_INFO":
            return self._format_airport_info(raw_data, icao)
        elif data_type == "NOTAM":
            return self._format_notam_info(raw_data, icao)
        else:
            return str(raw_data)

    def _format_airport_info(self, airport_data: Dict[str, Any], icao: str) -> str:
        formatted = [f"**AERÓDROMO {icao}:**"]
        if 'name' in airport_data:
            formatted.append(f"Nome: {airport_data['name']}")
        if 'city' in airport_data:
            formatted.append(f"Cidade: {airport_data['city']}")
        if 'country' in airport_data:
            formatted.append(f"País: {airport_data['country']}")
        if 'elevation' in airport_data:
            formatted.append(f"Elevação: {airport_data['elevation']} ft")
        if 'coordinates' in airport_data:
            coords = airport_data['coordinates']
            formatted.append(f"Coordenadas: {coords.get('lat', 'N/A')}, {coords.get('lon', 'N/A')}")
        return '\n'.join(formatted)

    def _format_notam_info(self, notam_data: Dict[str, Any], icao: str) -> str:
        formatted = [f"**NOTAM {icao}:**"]
        if 'text' in notam_data:
            formatted.append(f"Texto: {notam_data['text']}")
        if 'valid_from' in notam_data:
            formatted.append(f"Válido de: {notam_data['valid_from']}")
        if 'valid_to' in notam_data:
            formatted.append(f"Válido até: {notam_data['valid_to']}")
        return '\n'.join(formatted)

    def _build_geographic_response(self, validated_data: Dict[str, Any], geographic_type: str) -> str:
        if validated_data['validation'] == 'no_data':
            return "⚠ Nenhuma informação geográfica encontrada nas fontes consultadas."
        if validated_data['validation'] == 'insufficient_data':
            return "⚠ Informação geográfica insuficiente nas fontes consultadas."
        content = validated_data['content']
        response = f"**INFORMAÇÕES GEOGRÁFICAS - {geographic_type.upper()}**\n\n{content}"
        return response

# =============================
# 8. OPERATIONS AGENT
# =============================
class OperationsAgent(BaseAuxiliaryAgent):
    """
    Agente Auxiliar 8 - Planejamento de Voo Operacional
    Especializado em rotas, combustível, alternados, ETOPS, RVSM, PBN
    """
    def __init__(self):
        super().__init__("OperationsAgent", "Planejamento de Voo Operacional")
        handoff_manager.register_agent(AgentEnum.OPERATIONS, self)

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        try:
            operations_type = self._identify_operations_type(request.query)
            icao_codes = request.entities.get('icao_codes', [])
            operations_data = await self._query_operations_sources(operations_type, icao_codes)
            validated_data = self._validate_operations_data(operations_data, operations_type)
            response_content = self._build_operations_response(validated_data, operations_type)
            return AgentResponse(
                agent_name=self.agent_name,
                content=response_content,
                sources=self._format_sources(validated_data.get('sources', [])),
                confidence=validated_data.get('confidence', 0.8),
                reasoning=f"Consulta operacional {operations_type} para {len(icao_codes)} aeródromos",
                success=True,
                timestamp=datetime.now(timezone.utc),
                additional_data={
                    "operations_type": operations_type,
                    "icao_codes": icao_codes
                }
            )
        except Exception as e:
            return AgentResponse(
                agent_name=self.agent_name,
                content="⚠ Informação operacional não disponível nas fontes oficiais consultadas. Recomenda-se consultar AIP Brasil ou documentação operacional.",
                sources=[],
                confidence=0.0,
                reasoning=f"Erro no processamento: {str(e)}",
                success=False,
                timestamp=datetime.now(timezone.utc),
                error_message=str(e)
            )

    def _identify_operations_type(self, query: str) -> str:
        query_lower = query.lower()
        if any(term in query_lower for term in ['planejamento', 'plano de voo']):
            return "PLANEJAMENTO"
        elif any(term in query_lower for term in ['rota', 'route']):
            return "ROTA"
        elif any(term in query_lower for term in ['combustível', 'fuel']):
            return "COMBUSTIVEL"
        elif any(term in query_lower for term in ['alternado', 'alternate']):
            return "ALTERNADOS"
        elif any(term in query_lower for term in ['etops']):
            return "ETOPS"
        elif any(term in query_lower for term in ['rvsm']):
            return "RVSM"
        elif any(term in query_lower for term in ['pbn', 'rnav']):
            return "PBN"
        else:
            return "GERAL"

    async def _query_operations_sources(self, operations_type: str, icao_codes: List[str]) -> List[Dict[str, Any]]:
        operations_data = []
        try:
            result = await pinecone_server.search_knowledge(
                query=f"{operations_type} {' '.join(icao_codes)}",
                namespace="Planejamento_de_Voo",
                top_k=5
            )
            if result.get('success') and result.get('matches'):
                operations_data.extend(result['matches'])
            if len(icao_codes) >= 2 and operations_type in ["ROTA", "PLANEJAMENTO"]:
                try:
                    result = await rapidapi_distance_server.calculate_route_distance(
                        origin=icao_codes[0],
                        destination=icao_codes[1]
                    )
                    if result.get('success'):
                        operations_data.append({
                            'type': 'DISTANCE',
                            'data': result.get('data'),
                            'source': 'RapidAPI Distance'
                        })
                except Exception as e:
                    self._log_action(
                        "distance_query_error",
                        f"Erro na consulta de distância: {str(e)}",
                        False
                    )
        except Exception as e:
            self._log_action(
                "operations_query_error",
                f"Erro na consulta operacional: {str(e)}",
                False
            )
        return operations_data

    def _validate_operations_data(self, operations_data: List[Dict[str, Any]], operations_type: str) -> Dict[str, Any]:
        if not operations_data:
            return {
                'content': '',
                'sources': [],
                'confidence': 0.0,
                'validation': 'no_data'
            }
        consolidated_content = []
        sources_list = []
        for data in operations_data:
            if isinstance(data, dict):
                if 'content' in data:
                    content = data.get('content', '').strip()
                    source = data.get('source', 'Planejamento de Voo')
                    if content:
                        consolidated_content.append(content)
                        sources_list.append(source)
                else:
                    data_type = data.get('type', '')
                    raw_data = data.get('data', {})
                    source = data.get('source', '')
                    if raw_data:
                        formatted_data = self._format_operations_data(raw_data, data_type)
                        if formatted_data:
                            consolidated_content.append(formatted_data)
                            sources_list.append(source)
        confidence = min(0.85, len(consolidated_content) * 0.3)
        return {
            'content': '\n\n'.join(consolidated_content),
            'sources': sources_list,
            'confidence': confidence,
            'validation': 'validated' if consolidated_content else 'insufficient_data'
        }

    def _format_operations_data(self, raw_data: Dict[str, Any], data_type: str) -> str:
        if data_type == "DISTANCE":
            return self._format_distance_data(raw_data)
        else:
            return str(raw_data)

    def _format_distance_data(self, distance_data: Dict[str, Any]) -> str:
        formatted = ["**INFORMAÇÕES DE ROTA:**"]
        if 'distance' in distance_data:
            formatted.append(f"Distância: {distance_data['distance']}")
        if 'bearing' in distance_data:
            formatted.append(f"Rumo: {distance_data['bearing']}")
        if 'flight_time' in distance_data:
            formatted.append(f"Tempo estimado: {distance_data['flight_time']}")
        return '\n'.join(formatted)

    def _build_operations_response(self, validated_data: Dict[str, Any], operations_type: str) -> str:
        if validated_data['validation'] == 'no_data':
            return "⚠ Nenhuma informação operacional encontrada nas fontes consultadas."
        if validated_data['validation'] == 'insufficient_data':
            return "⚠ Informação operacional insuficiente nas fontes consultadas."
        content = validated_data['content']
        response = f"**OPERAÇÕES - {operations_type.upper()}**\n\n{content}"
        return response

# =============================
# REGISTRY DOS AGENTES
# =============================
auxiliary_agents = {
    "regulatory_agent": RegulatoryAgent(),
    "weather_agent": WeatherAgent(),
    "performance_agent": PerformanceAgent(),
    "technical_agent": TechnicalAgent(),
    "education_agent": EducationAgent(),
    "communication_agent": CommunicationAgent(),
    "geographic_agent": GeographicAgent(),
    "operations_agent": OperationsAgent()
}

async def get_auxiliary_agent(agent_name: str) -> Optional[BaseAuxiliaryAgent]:
    return auxiliary_agents.get(agent_name)

async def execute_auxiliary_agent(agent_name: str, request: AgentRequest) -> AgentResponse:
    agent = await get_auxiliary_agent(agent_name)
    if not agent:
        return AgentResponse(
            agent_name=agent_name,
            content=f"⚠ Agente {agent_name} não encontrado ou não implementado.",
            sources=[],
            confidence=0.0,
            reasoning=f"Agente {agent_name} não disponível",
            success=False,
            timestamp=datetime.now(timezone.utc),
            error_message=f"Agente {agent_name} não encontrado"
        )
    return await agent.process_request(request) 