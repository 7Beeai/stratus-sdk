import asyncio
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone

from src.utils.logging import get_logger
from config.settings import get_settings

logger = get_logger()
settings = get_settings()

class MessageCategory(Enum):
    """Categorias de mensagens para roteamento - baseadas no prompt original"""
    REGULATORY = "regulatory"                    # Regulamentação Aeronáutica
    TECHNICAL = "technical"                      # Aeronaves e Manuais Técnicos
    WEATHER = "weather"                          # Meteorologia e Informações Operacionais
    GEOGRAPHIC = "geographic"                    # Localização e Adaptação Geográfica
    PERFORMANCE = "performance"                  # Peso, Balanceamento e Performance
    OPERATIONS = "operations"                    # Planejamento de Voo Operacional
    EDUCATION = "education"                      # Educação e Carreira Aeronáutica
    COMMUNICATION = "communication"              # Comunicação Técnica e Didática
    SOCIAL = "social"                           # Interação Social e Conversa Humanizada

class UrgencyLevel(Enum):
    """Níveis de urgência para priorização"""
    EMERGENCY = "emergency"      # Emergência (MAYDAY, PAN-PAN)
    URGENT = "urgent"           # Urgente (Operacional crítico)
    HIGH = "high"               # Alta (Planejamento de voo)
    NORMAL = "normal"           # Normal (Educacional, técnico)
    LOW = "low"                 # Baixa (Social, curiosidade)

@dataclass
class MessageClassification:
    """Resultado da classificação de mensagem"""
    primary_category: MessageCategory
    secondary_categories: List[MessageCategory]
    urgency: UrgencyLevel
    confidence: float
    entities: Dict[str, List[str]]
    recommended_agents: List[str]
    reasoning: str
    requires_multiple_agents: bool
    estimated_complexity: str
    chain_of_thought: str

@dataclass
class ExtractedEntities:
    """Entidades extraídas da mensagem"""
    icao_codes: List[str]
    aircraft_types: List[str]
    regulations: List[str]
    weather_terms: List[str]
    technical_terms: List[str]
    locations: List[str]
    dates_times: List[str]
    flight_levels: List[str]
    emergency_terms: List[str]

class StratusRouterAgent:
    """
    Stratus.IA Router Agent - Classificador Inteligente de Mensagens
    
    Baseado no prompt original do Stratus.IA, responsável por:
    - Classificar mensagens por categoria e urgência
    - Extrair entidades relevantes (ICAO, aeronaves, etc.)
    - Determinar agentes especialistas necessários
    - Priorizar processamento por criticidade
    - Aplicar Chain-of-Thought para análise
    """
    
    def __init__(self):
        self.name = "StratusRouterAgent"
        
        # Padrões regex para extração de entidades - melhorados
        self.patterns = {
            'icao_codes': r'\b[A-Z]{4}\b',
            'aircraft_types': r'\b(?:B737|B777|B787|A320|A330|A350|E190|E195|ATR72|ATR42|C172|PA28|BE58|PC12|CITATION|KING AIR|CARAVAN|EMBRAER|BOEING|AIRBUS)\b',
            'regulations': r'\bRBAC[-\s]?(\d+)\b|\bIS[-\s]?(\d+)\b|\bANNEX[-\s]?(\d+)\b|\bAIP[-\s]?(?:GEN|ENR|AD)\b',
            'weather_terms': r'\b(?:METAR|TAF|SIGMET|GAMET|AIRMET|CB|TS|TURB|ICE|LLWS|VIS|CAVOK|BKN|OVC|SCT|FEW)\b',
            'flight_levels': r'\bFL\d{3}\b|\b\d{1,2}000\s?(?:FT|PÉS|FEET)\b',
            'emergency_terms': r'\b(?:MAYDAY|PAN-PAN|EMERGENCY|EMERGÊNCIA|SOCORRO|DISTRESS|URGENCY)\b',
            'urgent_terms': r'\b(?:URGENT|URGENTE|IMEDIATO|CRÍTICO|FALHA|FAILURE|MALFUNCTION|AVARIA)\b',
            'performance_terms': r'\b(?:PESO|WEIGHT|CG|BALANCE|PERFORMANCE|DECOLAGEM|TAKEOFF|POUSO|LANDING|COMBUSTÍVEL|FUEL)\b',
            'operational_terms': r'\b(?:PLANEJAMENTO|PLANNING|ROTA|ROUTE|ALTERNADO|ALTERNATE|ETOPS|RVSM|PBN|PLANO DE VOO|FLIGHT PLAN)\b'
        }
        
        # Palavras comuns que são 4 letras mas não são códigos ICAO
        self.common_four_letter_words = {
            'PARA', 'ROTA', 'VOO', 'AIP', 'ANAC', 'ICAO', 'RBAC', 'SIGMET', 'GAMET', 'AIRMET',
            'COMO', 'PESO', 'HOJE', 'AMANHÃ', 'ONTEM', 'AQUI', 'LÁ', 'CÁ', 'SIM', 'NÃO',
            'QUAL', 'QUEM', 'ONDE', 'QUANDO', 'PORQUE', 'PARA', 'COMO', 'MUITO', 'POUCO',
            'ALTO', 'BAIXO', 'LONGO', 'CURTO', 'RÁPIDO', 'LENTO', 'FRIO', 'QUENTE', 'NOVO',
            'VELHO', 'BOM', 'RUIM', 'FÁCIL', 'DIFÍCIL', 'CLARO', 'ESCURO', 'CHEIO', 'VAZIO'
        }
        
        # Keywords para classificação por categoria - baseadas no prompt original
        self.category_keywords = {
            MessageCategory.REGULATORY: [
                'rbac', 'regulamentação', 'norma', 'anac', 'icao', 'licença', 'habilitação',
                'certificado', 'autorização', 'aprovação', 'homologação', 'is', 'anexo',
                'normativo', 'procedimento', 'requisito', 'obrigatório', 'permitido', 'proibido'
            ],
            MessageCategory.TECHNICAL: [
                'aeronave', 'aircraft', 'poh', 'afm', 'qrh', 'mel', 'sistema', 'equipamento',
                'motor', 'engine', 'avionics', 'instrumentos', 'manual', 'procedimento', 'checklist',
                'service bulletin', 'advisory', 'limitação', 'restrição', 'sistema', 'componente'
            ],
            MessageCategory.WEATHER: [
                'metar', 'taf', 'tempo', 'meteorologia', 'vento', 'wind', 'visibilidade', 'visibility',
                'nuvem', 'cloud', 'chuva', 'rain', 'trovoada', 'thunderstorm', 'turbulência', 'turbulence',
                'gelo', 'ice', 'sigmet', 'gamet', 'redemet', 'aisweb', 'aip met', 'trend'
            ],
            MessageCategory.GEOGRAPHIC: [
                'aeródromo', 'airport', 'fir', 'localização', 'coordenadas', 'carta', 'chart',
                'notam', 'aip', 'rota', 'waypoint', 'navegação', 'posição', 'geográfica',
                'fronteira', 'relevo', 'terreno', 'adaptação', 'local'
            ],
            MessageCategory.PERFORMANCE: [
                'peso', 'weight', 'balanceamento', 'balance', 'cg', 'performance', 'decolagem', 'takeoff',
                'pouso', 'landing', 'combustível', 'fuel', 'alcance', 'range', 'teto', 'ceiling',
                'velocidade', 'speed', 'cálculo', 'calculation', 'limitação', 'limitation'
            ],
            MessageCategory.OPERATIONS: [
                'planejamento', 'planning', 'voo', 'flight', 'rota', 'route', 'alternado', 'alternate',
                'combustível', 'fuel', 'reserva', 'reserve', 'etops', 'rvsm', 'pbn', 'plano de voo',
                'flight plan', 'operacional', 'operational', 'trip', 'contingência', 'contingency'
            ],
            MessageCategory.EDUCATION: [
                'curso', 'course', 'treinamento', 'training', 'licença', 'license', 'habilitação', 'rating',
                'exame', 'exam', 'prova', 'test', 'carreira', 'career', 'formação', 'formation',
                'instrutor', 'instructor', 'aluno', 'student', 'escola', 'school', 'academia', 'academy',
                'rbac 61', 'rbac 65', 'portal anac'
            ],
            MessageCategory.COMMUNICATION: [
                'comunicação', 'communication', 'fraseologia', 'phraseology', 'radiotelefonia', 'radio',
                'atc', 'torre', 'tower', 'controle', 'control', 'frequência', 'frequency', 'canal', 'channel',
                'inglês', 'english', 'termo', 'term', 'definição', 'definition', 'vocabulário', 'vocabulary',
                'sigla', 'acronym', 'jargão', 'jargon'
            ],
            MessageCategory.SOCIAL: [
                'olá', 'oi', 'hello', 'hi', 'bom dia', 'good morning', 'boa tarde', 'good afternoon',
                'boa noite', 'good evening', 'obrigado', 'obrigada', 'thank you', 'thanks', 'valeu',
                'tchau', 'goodbye', 'até logo', 'see you', 'como vai', 'how are you', 'tudo bem',
                'how is it going', 'bate-papo', 'chat', 'conversa', 'conversation'
            ]
        }

    def extract_entities(self, message: str) -> ExtractedEntities:
        """Extrai entidades relevantes da mensagem"""
        message_upper = message.upper()
        
        entities = ExtractedEntities(
            icao_codes=[],
            aircraft_types=[],
            regulations=[],
            weather_terms=[],
            technical_terms=[],
            locations=[],
            dates_times=[],
            flight_levels=[],
            emergency_terms=[]
        )
        
        # Extrair códigos ICAO (excluir palavras comuns)
        icao_matches = re.findall(self.patterns['icao_codes'], message_upper)
        entities.icao_codes = [code for code in icao_matches if code not in self.common_four_letter_words]
        
        # Extrair tipos de aeronave
        aircraft_matches = re.findall(self.patterns['aircraft_types'], message_upper)
        entities.aircraft_types = list(set(aircraft_matches))
        
        # Extrair regulamentações
        reg_matches = re.findall(self.patterns['regulations'], message_upper)
        entities.regulations = []
        for match in reg_matches:
            if isinstance(match, tuple):
                if match[0]:  # RBAC
                    entities.regulations.append(f"RBAC {match[0]}")
                elif match[1]:  # IS
                    entities.regulations.append(f"IS {match[1]}")
            else:  # AIP
                entities.regulations.append(match)
        
        # Extrair termos meteorológicos
        weather_matches = re.findall(self.patterns['weather_terms'], message_upper)
        entities.weather_terms = list(set(weather_matches))
        
        # Extrair flight levels
        fl_matches = re.findall(self.patterns['flight_levels'], message_upper)
        entities.flight_levels = list(set(fl_matches))
        
        # Extrair termos de emergência
        emergency_matches = re.findall(self.patterns['emergency_terms'], message_upper)
        entities.emergency_terms = list(set(emergency_matches))
        
        return entities

    def determine_urgency(self, message: str, entities: ExtractedEntities) -> UrgencyLevel:
        """Determina nível de urgência da mensagem"""
        message_upper = message.upper()
        
        # Emergência - termos críticos
        if entities.emergency_terms:
            return UrgencyLevel.EMERGENCY
        
        # Urgente - termos urgentes ou falhas
        if re.search(self.patterns['urgent_terms'], message_upper):
            return UrgencyLevel.URGENT
        
        # Alta prioridade - indicadores operacionais críticos
        high_priority_indicators = [
            # Meteorologia crítica
            len(entities.weather_terms) > 0 and any(term in ['SIGMET', 'CB', 'TS'] for term in entities.weather_terms),
            # NOTAMs ou planejamento de voo
            'NOTAM' in message_upper,
            'PLANEJAMENTO' in message_upper and 'VOO' in message_upper,
            # Múltiplos aeródromos = planejamento
            len(entities.icao_codes) > 1,
            # Performance ou operações críticas
            re.search(self.patterns['performance_terms'], message_upper),
            re.search(self.patterns['operational_terms'], message_upper)
        ]
        
        if any(high_priority_indicators):
            return UrgencyLevel.HIGH
        
        # Baixa prioridade - interação social
        social_indicators = ['OLÁ', 'OI', 'BOM DIA', 'BOA TARDE', 'BOA NOITE', 'OBRIGADO', 'VALEU', 'TCHAU']
        if any(indicator in message_upper for indicator in social_indicators):
            return UrgencyLevel.LOW
        
        return UrgencyLevel.NORMAL

    def classify_message(self, message: str, entities: ExtractedEntities) -> Tuple[MessageCategory, List[MessageCategory], float]:
        """Classifica mensagem por categoria usando Chain-of-Thought"""
        message_lower = message.lower()
        category_scores = {}
        
        # Calcular scores para cada categoria
        for category, keywords in self.category_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in message_lower:
                    score += 1
            
            # Bonus por entidades específicas
            if category == MessageCategory.WEATHER and entities.weather_terms:
                score += len(entities.weather_terms) * 3
            elif category == MessageCategory.TECHNICAL and entities.aircraft_types:
                score += len(entities.aircraft_types) * 3
            elif category == MessageCategory.REGULATORY and entities.regulations:
                score += len(entities.regulations) * 3
            elif category == MessageCategory.GEOGRAPHIC and entities.icao_codes:
                score += len(entities.icao_codes) * 2
            elif category == MessageCategory.PERFORMANCE and re.search(self.patterns['performance_terms'], message_lower):
                score += 5
            elif category == MessageCategory.OPERATIONS and re.search(self.patterns['operational_terms'], message_lower):
                score += 5
            
            category_scores[category] = score
        
        # Determinar categoria principal
        primary_category = max(category_scores, key=category_scores.get)
        primary_score = category_scores[primary_category]
        
        # Determinar categorias secundárias (score > 0 e != primary)
        secondary_categories = [
            cat for cat, score in category_scores.items() 
            if score > 0 and cat != primary_category
        ]
        
        # Calcular confiança
        total_score = sum(category_scores.values())
        confidence = primary_score / total_score if total_score > 0 else 0.5
        
        return primary_category, secondary_categories, confidence

    def recommend_agents(self, primary_category: MessageCategory, 
                        secondary_categories: List[MessageCategory],
                        urgency: UrgencyLevel) -> List[str]:
        """Recomenda agentes especialistas baseado na classificação"""
        
        # Mapeamento categoria -> agente (baseado no prompt original)
        agent_mapping = {
            MessageCategory.REGULATORY: "regulatory_agent",
            MessageCategory.TECHNICAL: "technical_agent", 
            MessageCategory.WEATHER: "weather_agent",
            MessageCategory.GEOGRAPHIC: "communication_agent",  # Localização vai para Communication
            MessageCategory.PERFORMANCE: "operations_agent",    # Performance vai para Operations
            MessageCategory.OPERATIONS: "operations_agent",
            MessageCategory.EDUCATION: "education_agent",
            MessageCategory.COMMUNICATION: "communication_agent",
            MessageCategory.SOCIAL: None  # Não precisa de agente especialista
        }
        
        recommended_agents = []
        
        # Agente principal
        primary_agent = agent_mapping.get(primary_category)
        if primary_agent:
            recommended_agents.append(primary_agent)
        
        # Agentes secundários
        for category in secondary_categories:
            secondary_agent = agent_mapping.get(category)
            if secondary_agent and secondary_agent not in recommended_agents:
                recommended_agents.append(secondary_agent)
        
        # Para emergências, sempre incluir weather_agent
        if urgency == UrgencyLevel.EMERGENCY and "weather_agent" not in recommended_agents:
            recommended_agents.append("weather_agent")
        
        # Para operações críticas, incluir weather_agent se não estiver
        if urgency == UrgencyLevel.HIGH and primary_category in [MessageCategory.OPERATIONS, MessageCategory.PERFORMANCE]:
            if "weather_agent" not in recommended_agents:
                recommended_agents.append("weather_agent")
        
        return recommended_agents

    def generate_chain_of_thought(self, message: str, entities: ExtractedEntities,
                                primary_category: MessageCategory, 
                                secondary_categories: List[MessageCategory],
                                urgency: UrgencyLevel) -> str:
        """Gera Chain-of-Thought para análise da mensagem"""
        
        chain = f"**ANÁLISE CHAIN-OF-THOUGHT:**\n\n"
        
        # 1. Identificação da natureza da pergunta
        chain += f"1️⃣ **NATUREZA DA PERGUNTA:**\n"
        chain += f"   • Categoria Principal: {primary_category.value}\n"
        if secondary_categories:
            chain += f"   • Categorias Secundárias: {[cat.value for cat in secondary_categories]}\n"
        chain += f"   • Nível de Urgência: {urgency.value}\n\n"
        
        # 2. Entidades extraídas
        chain += f"2️⃣ **ENTIDADES IDENTIFICADAS:**\n"
        if entities.icao_codes:
            chain += f"   • Códigos ICAO: {entities.icao_codes}\n"
        if entities.aircraft_types:
            chain += f"   • Tipos de Aeronave: {entities.aircraft_types}\n"
        if entities.regulations:
            chain += f"   • Regulamentações: {entities.regulations}\n"
        if entities.weather_terms:
            chain += f"   • Termos Meteorológicos: {entities.weather_terms}\n"
        if entities.flight_levels:
            chain += f"   • Flight Levels: {entities.flight_levels}\n"
        if entities.emergency_terms:
            chain += f"   • Termos de Emergência: {entities.emergency_terms}\n"
        if not any([entities.icao_codes, entities.aircraft_types, entities.regulations, 
                   entities.weather_terms, entities.flight_levels, entities.emergency_terms]):
            chain += f"   • Nenhuma entidade específica identificada\n"
        chain += "\n"
        
        # 3. Atribuição ao especialista
        chain += f"3️⃣ **ATRIBUIÇÃO AO ESPECIALISTA:**\n"
        if primary_category == MessageCategory.SOCIAL:
            chain += f"   • Interação Social → Resposta direta do Stratus.IA\n"
        else:
            chain += f"   • {primary_category.value.title()} → Agente especializado\n"
        chain += "\n"
        
        # 4. Prioridade de fontes
        chain += f"4️⃣ **PRIORIDADE DE FONTES:**\n"
        chain += f"   • Banco interno STRATUS.IA\n"
        chain += f"   • Documentos ANAC (RBAC, IS), AIP Brasil, REDEMET, AISWEB\n"
        chain += f"   • Documentos ICAO/FAA/EASA/POH/AFM/manufacturer\n"
        chain += "\n"
        
        # 5. Validação e construção
        chain += f"5️⃣ **VALIDAÇÃO E CONSTRUÇÃO:**\n"
        chain += f"   • Cruzamento de fontes para validação\n"
        chain += f"   • Verificação de atualidade e aplicabilidade\n"
        chain += f"   • Construção da resposta segundo especialista ativo\n"
        
        return chain

    async def route_message(self, message: str, user_id: str = "system", 
                           context: Dict[str, Any] = None) -> MessageClassification:
        """Rota mensagem e retorna classificação completa"""
        
        # Log da mensagem recebida
        logger.log_agent_action(
            agent_name=self.name,
            action="route_message",
            message=f"Processando mensagem do usuário {user_id}",
            user_id=user_id,
            success=True,
            additional_context={"message_length": len(message)}
        )
        
        # Extrair entidades
        entities = self.extract_entities(message)
        
        # Determinar urgência
        urgency = self.determine_urgency(message, entities)
        
        # Classificar mensagem
        primary_category, secondary_categories, confidence = self.classify_message(message, entities)
        
        # Recomendar agentes
        recommended_agents = self.recommend_agents(primary_category, secondary_categories, urgency)
        
        # Gerar Chain-of-Thought
        chain_of_thought = self.generate_chain_of_thought(
            message, entities, primary_category, secondary_categories, urgency
        )
        
        # Determinar complexidade
        complexity_factors = [
            len(secondary_categories) > 1,
            len(entities.icao_codes) > 2,
            len(entities.aircraft_types) > 1,
            urgency in [UrgencyLevel.EMERGENCY, UrgencyLevel.URGENT],
            len(entities.regulations) > 1
        ]
        
        if sum(complexity_factors) >= 3:
            estimated_complexity = "high"
        elif sum(complexity_factors) >= 1:
            estimated_complexity = "medium"
        else:
            estimated_complexity = "low"
        
        # Gerar reasoning
        reasoning = f"Classificada como {primary_category.value} (confiança: {confidence:.2f}) "
        reasoning += f"com urgência {urgency.value}. "
        reasoning += f"Entidades: ICAO={entities.icao_codes}, Aircraft={entities.aircraft_types}. "
        reasoning += f"Agentes recomendados: {recommended_agents}"
        
        classification = MessageClassification(
            primary_category=primary_category,
            secondary_categories=secondary_categories,
            urgency=urgency,
            confidence=confidence,
            entities={
                "icao_codes": entities.icao_codes,
                "aircraft_types": entities.aircraft_types,
                "regulations": entities.regulations,
                "weather_terms": entities.weather_terms,
                "flight_levels": entities.flight_levels,
                "emergency_terms": entities.emergency_terms
            },
            recommended_agents=recommended_agents,
            reasoning=reasoning,
            requires_multiple_agents=len(recommended_agents) > 1,
            estimated_complexity=estimated_complexity,
            chain_of_thought=chain_of_thought
        )
        
        # Log da classificação
        logger.log_agent_action(
            agent_name=self.name,
            action="classify_message",
            message=f"Mensagem classificada: {primary_category.value} | Urgência: {urgency.value} | Agentes: {recommended_agents}",
            user_id=user_id,
            success=True,
            additional_context={
                "classification": classification.__dict__,
                "confidence": confidence,
                "complexity": estimated_complexity
            }
        )
        
        return classification

# Instância global do router
router_agent = StratusRouterAgent() 