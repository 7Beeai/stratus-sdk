import asyncio
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timezone
import json
import hashlib
import re
# from pinecone import Pinecone, ServerlessSpec  # Descomente quando Pinecone estiver instalado
# from openai import AsyncOpenAI  # Descomente quando OpenAI estiver instalado

from src.utils.logging import get_logger
from src.utils.base import CircuitBreaker, ExponentialBackoff, CacheManager
from config.settings import get_settings

logger = get_logger()
settings = get_settings()

class NamespaceCategory(Enum):
    """Categorias dos namespaces Pinecone"""
    REGULATION = "regulation"
    NAVIGATION = "navigation"
    AIRCRAFT = "aircraft"
    COMMUNICATION = "communication"
    EDUCATION = "education"

@dataclass
class NamespaceConfig:
    name: str
    tool_name: str
    description: str
    category: NamespaceCategory
    cache_ttl: int
    priority: int
    safety_critical: bool = False

@dataclass
class VectorSearchResult:
    namespace: str
    content: str
    metadata: Dict[str, Any]
    score: float
    source: str
    retrieved_at: datetime = None
    def __post_init__(self):
        if self.retrieved_at is None:
            self.retrieved_at = datetime.now(timezone.utc)

@dataclass
class PineconeResponse:
    query: str
    namespaces_searched: List[str]
    total_results: int
    results: List[VectorSearchResult]
    search_time_ms: float
    cache_hit: bool = False

class PineconeMCPServer:
    """Servidor MCP Pinecone - Base Vetorial de Conhecimento Aeronáutico"""
    def __init__(self):
        self.index_name = "stratus"
        self.embedding_model = "text-embedding-3-small"
        self.embedding_dimensions = 3072
        self.default_top_k = 10
        self.similarity_threshold = 0.75
        self.pinecone_client = None
        self.openai_client = None  # AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.index = None
        self.circuit_breakers = {}
        self.cache = CacheManager()
        self.backoff = ExponentialBackoff(
            initial_delay=0.5,
            max_delay=4.0,
            multiplier=2.0,
            jitter=True
        )
        self.namespaces = {
            # GRUPO 1: REGULAMENTAÇÃO E NORMAS
            "ANAC": NamespaceConfig(
                name="ANAC",
                tool_name="ANAC",
                description="Busca informações em vetores sobre temas relacionados à ANAC (Agência Nacional de Aviação Civil).",
                category=NamespaceCategory.REGULATION,
                cache_ttl=86400,
                priority=1,
                safety_critical=True
            ),
            "DECEA": NamespaceConfig(
                name="DECEA",
                tool_name="DECEA",
                description="Base vetorial para buscas semânticas sobre cartas, procedimentos, publicações e normas do DECEA.",
                category=NamespaceCategory.REGULATION,
                cache_ttl=86400,
                priority=1,
                safety_critical=True
            ),
            "ICAO e seus Anexos": NamespaceConfig(
                name="ICAO e seus Anexos",
                tool_name="ICAO",
                description="Base vetorial para consultas semânticas aos documentos da ICAO e seus Anexos, com foco em normas internacionais de aviação civil, segurança operacional, navegação e regulamentação técnica.",
                category=NamespaceCategory.REGULATION,
                cache_ttl=86400,
                priority=1,
                safety_critical=True
            ),
            "ProcedimentosOperacionais": NamespaceConfig(
                name="ProcedimentosOperacionais",
                tool_name="ProcedimentosOperacionais",
                description="Base vetorial dedicada a procedimentos padronizados de voo, listas de checagem, normas operacionais e boas práticas aplicadas em diferentes fases da operação aeronáutica.",
                category=NamespaceCategory.REGULATION,
                cache_ttl=43200,
                priority=2,
                safety_critical=True
            ),
            # GRUPO 2: NAVEGAÇÃO E CARTAS
            "AIP_Brasil_Map": NamespaceConfig(
                name="AIP_Brasil_Map",
                tool_name="AIP_Brasil_Map",
                description="Repositório vetorial para consultas a conteúdos do AIP Brasil, incluindo cartas aeronáuticas, procedimentos IFR/VFR, zonas de controle e informações geográficas para navegação aérea.",
                category=NamespaceCategory.NAVIGATION,
                cache_ttl=43200,
                priority=2,
                safety_critical=True
            ),
            "Jeppesen_Manuais": NamespaceConfig(
                name="Jeppesen_Manuais",
                tool_name="Jeppesen_Manuais",
                description="Repositório vetorial para buscas semânticas em manuais da Jeppesen, com foco em cartas aeronáuticas, briefings, procedimentos de voo e documentação complementar para navegação aérea.",
                category=NamespaceCategory.NAVIGATION,
                cache_ttl=43200,
                priority=2
            ),
            "Planejamento_de_Voo": NamespaceConfig(
                name="Planejamento_de_Voo",
                tool_name="PlanejamentoVoo",
                description="Base vetorial focada em rotas, navegação, combustível, alternados, condições meteorológicas e demais aspectos essenciais ao correto planejamento de voos VFR e IFR.",
                category=NamespaceCategory.NAVIGATION,
                cache_ttl=14400,
                priority=2,
                safety_critical=True
            ),
            # GRUPO 3: AERONAVES E SISTEMAS
            "Manuais_Aeronaves_Equipamentos": NamespaceConfig(
                name="Manuais_Aeronaves_Equipamentos",
                tool_name="Manuais_Aeronaves_Equipamentos",
                description="Base vetorial com dados técnicos e operacionais extraídos de POHs, AFMs e manuais de equipamentos aeronáuticos, abrangendo desempenho, limitações, procedimentos e sistemas específicos de cada modelo.",
                category=NamespaceCategory.AIRCRAFT,
                cache_ttl=604800,
                priority=2
            ),
            "InstrumentosAvionicosSistemasEletricos": NamespaceConfig(
                name="InstrumentosAvionicosSistemasEletricos",
                tool_name="InstrumentosAvionicosSistemasEletricos",
                description="Base vetorial para consultas sobre funcionamento, operação e integração de instrumentos de voo, sistemas aviônicos e circuitos elétricos em aeronaves.",
                category=NamespaceCategory.AIRCRAFT,
                cache_ttl=86400,
                priority=3
            ),
            "PesoBalanceamento_Performance": NamespaceConfig(
                name="PesoBalanceamento_Performance",
                tool_name="PesoBalanceamento_Performance",
                description="Repositório vetorial voltado para consultas sobre cálculos de peso e balanceamento, performance de aeronaves, tabelas operacionais e limites operacionais, conforme manuais e normas aeronáuticas vigentes.",
                category=NamespaceCategory.AIRCRAFT,
                cache_ttl=86400,
                priority=2,
                safety_critical=True
            ),
            # GRUPO 4: COMUNICAÇÃO E OPERAÇÕES ESPECIAIS
            "ComunicacoesAereas": NamespaceConfig(
                name="ComunicacoesAereas",
                tool_name="ComunicacoesAereas",
                description="Base vetorial focada em frases-padrão, fonia, procedimentos de radiocomunicação e terminologia empregada na aviação, conforme padrões nacionais e internacionais.",
                category=NamespaceCategory.COMMUNICATION,
                cache_ttl=86400,
                priority=2,
                safety_critical=True
            ),
            "Anfibios_HidroAvioes": NamespaceConfig(
                name="Anfibios_HidroAvioes",
                tool_name="Anfibios_HidroAvioes",
                description="Base vetorial dedicada a operações com aeronaves anfíbias e hidroaviões, cobrindo procedimentos específicos, performance, regulamentações e técnicas de operação em ambientes aquáticos.",
                category=NamespaceCategory.COMMUNICATION,
                cache_ttl=86400,
                priority=4
            ),
            "SoftSkills_Risk_Medical": NamespaceConfig(
                name="SoftSkills_Risk_Medical",
                tool_name="SoftSkills_Risk_Medical",
                description="Base vetorial voltada a competências não técnicas, tomada de decisão, CRM, gestão de risco e aspectos médicos relevantes para a segurança operacional na aviação.",
                category=NamespaceCategory.COMMUNICATION,
                cache_ttl=86400,
                priority=3,
                safety_critical=True
            ),
            # GRUPO 5: FORMAÇÃO E EDUCAÇÃO
            "MaterialFormacao_BancaANAC_Simulados": NamespaceConfig(
                name="MaterialFormacao_BancaANAC_Simulados",
                tool_name="MaterialFormacao_BancaANAC_Simulados",
                description="Base vetorial voltada para estudos teóricos, questões de banca da ANAC e simulados, ideal para alunos em formação e preparação para exames de licenças e habilitações aeronáuticas.",
                category=NamespaceCategory.EDUCATION,
                cache_ttl=43200,
                priority=3
            ),
            "InstrutoresDeVoo": NamespaceConfig(
                name="InstrutoresDeVoo",
                tool_name="InstrutoresDeVoo",
                description="Base vetorial com conteúdos voltados à instrução aérea, incluindo técnicas de ensino, regulamentações da ANAC, perfil do instrutor e boas práticas em formação de pilotos.",
                category=NamespaceCategory.EDUCATION,
                cache_ttl=86400,
                priority=3
            ),
            "Exame SDEA ICAO ANAC": NamespaceConfig(
                name="Exame SDEA ICAO ANAC",
                tool_name="Exame_SDEA_ICAO_ANAC",
                description="Base vetorial voltada à preparação para o exame de proficiência linguística SDEA, com foco nos critérios da ANAC e da ICAO, estrutura da prova, frases-padrão e simulações de comunicação em inglês aeronáutico.",
                category=NamespaceCategory.EDUCATION,
                cache_ttl=86400,
                priority=4
            ),
            "Miscelanea": NamespaceConfig(
                name="Miscelanea",
                tool_name="Miscelanea",
                description="Base vetorial com conteúdos diversos relacionados à aviação, incluindo temas complementares, curiosidades técnicas, históricos, contextos operacionais e materiais de apoio não categorizados.",
                category=NamespaceCategory.EDUCATION,
                cache_ttl=86400,
                priority=5
            ),
            # Demais namespaces serão adicionados nas próximas etapas
        }
        for namespace in self.namespaces.keys():
            self.circuit_breakers[namespace] = CircuitBreaker(
                failure_threshold=3,
                timeout_duration=10,
                half_open_max_calls=1
            )

    # Métodos de busca para os 4 primeiros namespaces
    async def search_anac(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca ANAC"""
        return await self.search_knowledge_base(query, ["ANAC"], top_k, user_id)

    async def search_decea(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca DECEA"""
        return await self.search_knowledge_base(query, ["DECEA"], top_k, user_id)

    async def search_icao(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca ICAO e Anexos"""
        return await self.search_knowledge_base(query, ["ICAO e seus Anexos"], top_k, user_id)

    async def search_procedures(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca Procedimentos Operacionais"""
        return await self.search_knowledge_base(query, ["ProcedimentosOperacionais"], top_k, user_id)

    # Métodos de busca para os namespaces dos Grupos 2 e 3
    async def search_aip_charts(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca AIP Brasil e cartas aeronáuticas"""
        return await self.search_knowledge_base(query, ["AIP_Brasil_Map"], top_k, user_id)

    async def search_jeppesen(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca manuais Jeppesen"""
        return await self.search_knowledge_base(query, ["Jeppesen_Manuais"], top_k, user_id)

    async def search_flight_planning(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca planejamento de voo"""
        return await self.search_knowledge_base(query, ["Planejamento_de_Voo"], top_k, user_id)

    async def search_aircraft_manuals(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca manuais de aeronaves e equipamentos"""
        return await self.search_knowledge_base(query, ["Manuais_Aeronaves_Equipamentos"], top_k, user_id)

    async def search_avionics(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca instrumentos, aviônicos e sistemas elétricos"""
        return await self.search_knowledge_base(query, ["InstrumentosAvionicosSistemasEletricos"], top_k, user_id)

    async def search_weight_balance(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca peso, balanceamento e performance"""
        return await self.search_knowledge_base(query, ["PesoBalanceamento_Performance"], top_k, user_id)

    # Métodos de busca para os namespaces dos Grupos 4 e 5
    async def search_communications(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca comunicações aeronáuticas e fraseologia"""
        return await self.search_knowledge_base(query, ["ComunicacoesAereas"], top_k, user_id)

    async def search_seaplanes(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca operações com anfíbios e hidroaviões"""
        return await self.search_knowledge_base(query, ["Anfibios_HidroAvioes"], top_k, user_id)

    async def search_soft_skills(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca soft skills, CRM, gestão de risco e aspectos médicos"""
        return await self.search_knowledge_base(query, ["SoftSkills_Risk_Medical"], top_k, user_id)

    async def search_training_material(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca material de formação, banca ANAC e simulados"""
        return await self.search_knowledge_base(query, ["MaterialFormacao_BancaANAC_Simulados"], top_k, user_id)

    async def search_flight_instructors(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca conteúdos para instrutores de voo"""
        return await self.search_knowledge_base(query, ["InstrutoresDeVoo"], top_k, user_id)

    async def search_sdea_exam(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca preparação para exame SDEA ICAO ANAC"""
        return await self.search_knowledge_base(query, ["Exame SDEA ICAO ANAC"], top_k, user_id)

    async def search_miscellaneous(self, query: str, top_k: int = 10, user_id: str = "system") -> PineconeResponse:
        """Busca conteúdos diversos de aviação"""
        return await self.search_knowledge_base(query, ["Miscelanea"], top_k, user_id)

    # Métodos multi-namespace
    async def search_regulations(self, query: str, top_k: int = 15, user_id: str = "system") -> PineconeResponse:
        """Busca em todos os namespaces de regulamentação"""
        regulation_namespaces = ["ANAC", "DECEA", "ICAO e seus Anexos", "ProcedimentosOperacionais"]
        return await self.search_knowledge_base(query, regulation_namespaces, top_k, user_id)

    async def search_navigation(self, query: str, top_k: int = 15, user_id: str = "system") -> PineconeResponse:
        """Busca em todos os namespaces de navegação"""
        navigation_namespaces = ["AIP_Brasil_Map", "Jeppesen_Manuais", "Planejamento_de_Voo"]
        return await self.search_knowledge_base(query, navigation_namespaces, top_k, user_id)

    async def search_aircraft_systems(self, query: str, top_k: int = 15, user_id: str = "system") -> PineconeResponse:
        """Busca em todos os namespaces de aeronaves e sistemas"""
        aircraft_namespaces = ["Manuais_Aeronaves_Equipamentos", "InstrumentosAvionicosSistemasEletricos", "PesoBalanceamento_Performance"]
        return await self.search_knowledge_base(query, aircraft_namespaces, top_k, user_id)

    async def search_education(self, query: str, top_k: int = 15, user_id: str = "system") -> PineconeResponse:
        """Busca em todos os namespaces de educação"""
        education_namespaces = ["MaterialFormacao_BancaANAC_Simulados", "InstrutoresDeVoo", "Exame SDEA ICAO ANAC", "Miscelanea"]
        return await self.search_knowledge_base(query, education_namespaces, top_k, user_id)

    async def search_safety_critical(self, query: str, top_k: int = 20, user_id: str = "system") -> PineconeResponse:
        """Busca em todos os namespaces críticos para segurança"""
        safety_namespaces = [ns for ns, config in self.namespaces.items() if config.safety_critical]
        return await self.search_knowledge_base(query, safety_namespaces, top_k, user_id)

    # O restante da implementação será adicionado nas próximas etapas.

    async def __aenter__(self):
        """Async context manager entry"""
        # Initialize Pinecone client
        # self.pinecone_client = Pinecone(api_key=settings.PINECONE_API_KEY)
        # self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Get index
        try:
            # self.index = self.pinecone_client.Index(self.index_name)
            
            # Verify index health
            # stats = self.index.describe_index_stats()
            logger.log_agent_action(
                agent_name="PineconeMCPServer",
                action="initialize",
                message=f"Conectado ao índice '{self.index_name}' com {len(self.namespaces)} namespaces configurados",
                user_id="system",
                success=True
            )
            
        except Exception as e:
            logger.log_agent_action(
                agent_name="PineconeMCPServer",
                action="initialize",
                message=f"Erro ao conectar com Pinecone: {str(e)}",
                user_id="system",
                success=False
            )
            raise
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        pass

    def _generate_cache_key(self, query: str, namespaces: List[str], top_k: int) -> str:
        """Generate cache key for query"""
        key_data = {
            "query": query.lower().strip(),
            "namespaces": sorted(namespaces),
            "top_k": top_k
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _extract_aviation_context(self, query: str) -> Dict[str, Any]:
        """Extract aviation-specific context from query"""
        context = {
            "icao_codes": [],
            "aircraft_types": [],
            "regulations": [],
            "procedures": [],
            "safety_critical": False
        }
        
        # Extract ICAO codes (Brazilian format SBxx)
        icao_pattern = r'\bSB[A-Z]{2}\b'
        context["icao_codes"] = re.findall(icao_pattern, query.upper())
        
        # Extract aircraft types
        aircraft_pattern = r'\b(C172|PA28|BE58|EMB|A320|B737|ATR|CESSNA|PIPER|BEECH|EMBRAER|AIRBUS|BOEING)\w*\b'
        context["aircraft_types"] = re.findall(aircraft_pattern, query.upper())
        
        # Extract regulations
        regulation_pattern = r'\b(RBAC|IS|IAC|AIC|NOTAM|AD|SB)\s*[-\s]*\d+\b'
        context["regulations"] = re.findall(regulation_pattern, query.upper())
        
        # Detect safety-critical keywords
        safety_keywords = [
            'emergência', 'emergency', 'falha', 'failure', 'pane', 'mayday', 'pan pan',
            'segurança', 'safety', 'risco', 'risk', 'perigo', 'danger', 'crítico', 'critical'
        ]
        context["safety_critical"] = any(keyword in query.lower() for keyword in safety_keywords)
        
        return context

    def _select_relevant_namespaces(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Intelligently select relevant namespaces based on query context"""
        relevant_namespaces = []
        query_lower = query.lower()
        
        # Always include safety-critical namespaces for safety queries
        if context["safety_critical"]:
            safety_namespaces = [ns for ns, config in self.namespaces.items() if config.safety_critical]
            relevant_namespaces.extend(safety_namespaces)
        
        # Regulation-related keywords
        regulation_keywords = ['rbac', 'anac', 'decea', 'icao', 'regulament', 'norma', 'is ', 'iac']
        if any(keyword in query_lower for keyword in regulation_keywords):
            relevant_namespaces.extend(['ANAC', 'DECEA', 'ICAO e seus Anexos', 'ProcedimentosOperacionais'])
        
        # Navigation-related keywords
        navigation_keywords = ['carta', 'aip', 'jeppesen', 'navegação', 'rota', 'planejamento', 'ifr', 'vfr']
        if any(keyword in query_lower for keyword in navigation_keywords):
            relevant_namespaces.extend(['AIP_Brasil_Map', 'Jeppesen_Manuais', 'Planejamento_de_Voo'])
        
        # Aircraft-related keywords
        aircraft_keywords = ['aeronave', 'aircraft', 'manual', 'poh', 'afm', 'performance', 'peso', 'balanceamento']
        if any(keyword in query_lower for keyword in aircraft_keywords) or context["aircraft_types"]:
            relevant_namespaces.extend(['Manuais_Aeronaves_Equipamentos', 'InstrumentosAvionicosSistemasEletricos', 'PesoBalanceamento_Performance'])
        
        # Communication-related keywords
        comm_keywords = ['comunicação', 'fonia', 'radio', 'fraseologia', 'atc', 'torre', 'controle']
        if any(keyword in query_lower for keyword in comm_keywords):
            relevant_namespaces.extend(['ComunicacoesAereas'])
        
        # Education-related keywords
        education_keywords = ['exame', 'prova', 'simulado', 'questão', 'estudo', 'formação', 'instrutor', 'sdea']
        if any(keyword in query_lower for keyword in education_keywords):
            relevant_namespaces.extend(['MaterialFormacao_BancaANAC_Simulados', 'InstrutoresDeVoo', 'Exame SDEA ICAO ANAC'])
        
        # Special operations
        if any(keyword in query_lower for keyword in ['anfíbio', 'hidroavião', 'aquático']):
            relevant_namespaces.append('Anfibios_HidroAvioes')
        
        if any(keyword in query_lower for keyword in ['crm', 'soft skill', 'médico', 'risco']):
            relevant_namespaces.append('SoftSkills_Risk_Medical')
        
        # Remove duplicates and ensure we have at least some namespaces
        relevant_namespaces = list(set(relevant_namespaces))
        
        # If no specific namespaces identified, use high-priority ones
        if not relevant_namespaces:
            relevant_namespaces = [ns for ns, config in self.namespaces.items() if config.priority <= 2]
        
        # Limit to maximum 8 namespaces for performance
        if len(relevant_namespaces) > 8:
            # Sort by priority and safety criticality
            sorted_namespaces = sorted(
                relevant_namespaces,
                key=lambda ns: (
                    0 if self.namespaces[ns].safety_critical else 1,
                    self.namespaces[ns].priority
                )
            )
            relevant_namespaces = sorted_namespaces[:8]
        
        return relevant_namespaces

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI"""
        try:
            # Mock embedding for now - replace with actual OpenAI call
            # response = await self.openai_client.embeddings.create(
            #     model=self.embedding_model,
            #     input=text,
            #     dimensions=self.embedding_dimensions
            # )
            # return response.data[0].embedding
            
            # Mock embedding (random vector for testing)
            import random
            random.seed(hash(text) % 2**32)
            return [random.uniform(-1, 1) for _ in range(self.embedding_dimensions)]
            
        except Exception as e:
            logger.log_agent_action(
                agent_name="PineconeMCPServer",
                action="generate_embedding",
                message=f"Erro ao gerar embedding: {str(e)}",
                user_id="system",
                success=False
            )
            raise

    async def _search_namespace(self, query_embedding: List[float], namespace: str, 
                               top_k: int, user_id: str) -> List[VectorSearchResult]:
        """Search a specific namespace with circuit breaker"""
        
        @self.circuit_breakers[namespace]
        async def _search():
            try:
                # Mock search response for now - replace with actual Pinecone call
                # search_response = self.index.query(
                #     vector=query_embedding,
                #     top_k=top_k,
                #     namespace=namespace,
                #     include_metadata=True,
                #     include_values=False
                # )
                
                # Mock results for testing
                import random
                results = []
                for i in range(min(top_k, 5)):
                    score = random.uniform(0.75, 0.95)
                    if score >= self.similarity_threshold:
                        result = VectorSearchResult(
                            namespace=namespace,
                            content=f"Conteúdo mock do namespace {namespace} - resultado {i+1}",
                            metadata={
                                'text': f"Conteúdo mock do namespace {namespace} - resultado {i+1}",
                                'source': f'mock_{namespace}_{i}',
                                'category': self.namespaces[namespace].category.value
                            },
                            score=score,
                            source=f"Pinecone:{namespace}"
                        )
                        results.append(result)
                
                return results
                
            except Exception as e:
                logger.log_agent_action(
                    agent_name="PineconeMCPServer",
                    action="search_namespace",
                    message=f"Erro ao buscar no namespace {namespace}: {str(e)}",
                    user_id=user_id,
                    success=False
                )
                raise
        
        # Retry logic with exponential backoff
        for attempt in range(3):
            try:
                return await _search()
            except Exception as e:
                if attempt == 2:  # Last attempt
                    # Log safety violation for critical namespaces
                    if self.namespaces[namespace].safety_critical:
                        logger.log_safety_violation(
                            violation_type="CRITICAL_NAMESPACE_FAILURE",
                            message=f"Falha crítica no namespace {namespace}: {str(e)}",
                            agent_name="PineconeMCPServer",
                            user_id=user_id,
                            severity="HIGH"
                        )
                    return []  # Return empty results instead of failing
                
                delay = self.backoff.get_delay(attempt)
                await asyncio.sleep(delay)

    async def search_knowledge_base(self, query: str, namespaces: Optional[List[str]] = None, 
                                   top_k: int = None, user_id: str = "system") -> PineconeResponse:
        """Search the knowledge base across specified namespaces"""
        
        start_time = datetime.now()
        
        if top_k is None:
            top_k = self.default_top_k
        
        # Extract aviation context
        context = self._extract_aviation_context(query)
        
        # Select relevant namespaces if not specified
        if namespaces is None:
            namespaces = self._select_relevant_namespaces(query, context)
        
        # Validate namespaces
        valid_namespaces = [ns for ns in namespaces if ns in self.namespaces]
        if not valid_namespaces:
            raise ValueError(f"Nenhum namespace válido fornecido. Disponíveis: {list(self.namespaces.keys())}")
        
        # Check cache
        cache_key = self._generate_cache_key(query, valid_namespaces, top_k)
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            cached_response = PineconeResponse(**cached_data)
            cached_response.cache_hit = True
            return cached_response
        
        try:
            # Generate embedding
            query_embedding = await self._generate_embedding(query)
            
            # Search all namespaces in parallel
            search_tasks = []
            for namespace in valid_namespaces:
                task = self._search_namespace(query_embedding, namespace, top_k, user_id)
                search_tasks.append(task)
            
            # Wait for all searches to complete
            namespace_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # Combine and rank results
            all_results = []
            successful_namespaces = []
            
            for i, results in enumerate(namespace_results):
                namespace = valid_namespaces[i]
                if isinstance(results, Exception):
                    logger.log_agent_action(
                        agent_name="PineconeMCPServer",
                        action="search_namespace",
                        message=f"Falha no namespace {namespace}: {str(results)}",
                        user_id=user_id,
                        success=False
                    )
                    continue
                
                successful_namespaces.append(namespace)
                
                # Apply priority boost for safety-critical namespaces
                for result in results:
                    if self.namespaces[namespace].safety_critical and context["safety_critical"]:
                        result.score *= 1.1  # 10% boost for safety-critical content
                    
                    all_results.append(result)
            
            # Sort by score (descending) and limit results
            all_results.sort(key=lambda x: x.score, reverse=True)
            final_results = all_results[:top_k * 2]  # Allow more results for better ranking
            
            # Calculate search time
            search_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            response = PineconeResponse(
                query=query,
                namespaces_searched=successful_namespaces,
                total_results=len(final_results),
                results=final_results,
                search_time_ms=search_time_ms,
                cache_hit=False
            )
            
            # Cache result with appropriate TTL
            min_ttl = min(self.namespaces[ns].cache_ttl for ns in successful_namespaces)
            await self.cache.set(cache_key, asdict(response), min_ttl)
            
            # Log successful search
            logger.log_agent_action(
                agent_name="PineconeMCPServer",
                action="search_knowledge_base",
                message=f"Busca realizada em {len(successful_namespaces)} namespaces: {len(final_results)} resultados em {search_time_ms:.1f}ms",
                user_id=user_id,
                success=True,
                additional_context={
                    "query": query,
                    "namespaces": successful_namespaces,
                    "results_count": len(final_results),
                    "search_time_ms": search_time_ms,
                    "aviation_context": context
                }
            )
            
            return response
            
        except Exception as e:
            logger.log_agent_action(
                agent_name="PineconeMCPServer",
                action="search_knowledge_base",
                message=f"Erro na busca vetorial: {str(e)}",
                user_id=user_id,
                success=False
            )
            raise

# ==================== MCP TOOLS INTERFACE ====================

# Ferramentas individuais por namespace
async def search_anac_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em regulamentações ANAC"""
    async with PineconeMCPServer() as server:
        result = await server.search_anac(query, top_k, user_id)
        return asdict(result)

async def search_decea_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em documentos DECEA"""
    async with PineconeMCPServer() as server:
        result = await server.search_decea(query, top_k, user_id)
        return asdict(result)

async def search_icao_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em documentos ICAO"""
    async with PineconeMCPServer() as server:
        result = await server.search_icao(query, top_k, user_id)
        return asdict(result)

async def search_procedures_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em procedimentos operacionais"""
    async with PineconeMCPServer() as server:
        result = await server.search_procedures(query, top_k, user_id)
        return asdict(result)

async def search_aip_charts_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em AIP Brasil e cartas"""
    async with PineconeMCPServer() as server:
        result = await server.search_aip_charts(query, top_k, user_id)
        return asdict(result)

async def search_jeppesen_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em manuais Jeppesen"""
    async with PineconeMCPServer() as server:
        result = await server.search_jeppesen(query, top_k, user_id)
        return asdict(result)

async def search_flight_planning_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em planejamento de voo"""
    async with PineconeMCPServer() as server:
        result = await server.search_flight_planning(query, top_k, user_id)
        return asdict(result)

async def search_aircraft_manuals_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em manuais de aeronaves"""
    async with PineconeMCPServer() as server:
        result = await server.search_aircraft_manuals(query, top_k, user_id)
        return asdict(result)

async def search_avionics_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em aviônicos e instrumentos"""
    async with PineconeMCPServer() as server:
        result = await server.search_avionics(query, top_k, user_id)
        return asdict(result)

async def search_weight_balance_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em peso, balanceamento e performance"""
    async with PineconeMCPServer() as server:
        result = await server.search_weight_balance(query, top_k, user_id)
        return asdict(result)

async def search_communications_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em comunicações aeronáuticas"""
    async with PineconeMCPServer() as server:
        result = await server.search_communications(query, top_k, user_id)
        return asdict(result)

async def search_seaplanes_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em operações com hidroaviões"""
    async with PineconeMCPServer() as server:
        result = await server.search_seaplanes(query, top_k, user_id)
        return asdict(result)

async def search_soft_skills_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em soft skills e gestão de risco"""
    async with PineconeMCPServer() as server:
        result = await server.search_soft_skills(query, top_k, user_id)
        return asdict(result)

async def search_training_material_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em material de formação e exames"""
    async with PineconeMCPServer() as server:
        result = await server.search_training_material(query, top_k, user_id)
        return asdict(result)

async def search_flight_instructors_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em materiais para instrutores"""
    async with PineconeMCPServer() as server:
        result = await server.search_flight_instructors(query, top_k, user_id)
        return asdict(result)

async def search_sdea_exam_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em materiais do exame SDEA"""
    async with PineconeMCPServer() as server:
        result = await server.search_sdea_exam(query, top_k, user_id)
        return asdict(result)

async def search_miscellaneous_tool(query: str, top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em conteúdos diversos"""
    async with PineconeMCPServer() as server:
        result = await server.search_miscellaneous(query, top_k, user_id)
        return asdict(result)

# Ferramentas multi-namespace
async def search_regulations_tool(query: str, top_k: int = 15, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em todos os namespaces de regulamentação"""
    async with PineconeMCPServer() as server:
        result = await server.search_regulations(query, top_k, user_id)
        return asdict(result)

async def search_navigation_tool(query: str, top_k: int = 15, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em todos os namespaces de navegação"""
    async with PineconeMCPServer() as server:
        result = await server.search_navigation(query, top_k, user_id)
        return asdict(result)

async def search_aircraft_systems_tool(query: str, top_k: int = 15, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em todos os namespaces de aeronaves e sistemas"""
    async with PineconeMCPServer() as server:
        result = await server.search_aircraft_systems(query, top_k, user_id)
        return asdict(result)

async def search_education_tool(query: str, top_k: int = 15, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em todos os namespaces de educação"""
    async with PineconeMCPServer() as server:
        result = await server.search_education(query, top_k, user_id)
        return asdict(result)

async def search_safety_critical_tool(query: str, top_k: int = 20, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca em todos os namespaces críticos para segurança"""
    async with PineconeMCPServer() as server:
        result = await server.search_safety_critical(query, top_k, user_id)
        return asdict(result)

# Ferramenta de busca geral
async def search_knowledge_base_tool(query: str, namespaces: Optional[List[str]] = None, 
                                    top_k: int = 10, user_id: str = "system") -> Dict[str, Any]:
    """Ferramenta MCP para busca geral na base de conhecimento"""
    async with PineconeMCPServer() as server:
        result = await server.search_knowledge_base(query, namespaces, top_k, user_id)
        return asdict(result)

# Exportar TODAS as ferramentas MCP
MCP_TOOLS = {
    # Ferramentas individuais por namespace (17)
    "search_anac": search_anac_tool,
    "search_decea": search_decea_tool,
    "search_icao": search_icao_tool,
    "search_procedures": search_procedures_tool,
    "search_aip_charts": search_aip_charts_tool,
    "search_jeppesen": search_jeppesen_tool,
    "search_flight_planning": search_flight_planning_tool,
    "search_aircraft_manuals": search_aircraft_manuals_tool,
    "search_avionics": search_avionics_tool,
    "search_weight_balance": search_weight_balance_tool,
    "search_communications": search_communications_tool,
    "search_seaplanes": search_seaplanes_tool,
    "search_soft_skills": search_soft_skills_tool,
    "search_training_material": search_training_material_tool,
    "search_flight_instructors": search_flight_instructors_tool,
    "search_sdea_exam": search_sdea_exam_tool,
    "search_miscellaneous": search_miscellaneous_tool,
    
    # Ferramentas multi-namespace (5)
    "search_regulations": search_regulations_tool,
    "search_navigation": search_navigation_tool,
    "search_aircraft_systems": search_aircraft_systems_tool,
    "search_education": search_education_tool,
    "search_safety_critical": search_safety_critical_tool,
    
    # Ferramenta de busca geral (1)
    "search_knowledge_base": search_knowledge_base_tool
} 