import asyncio
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json

from .router import MessageClassification, MessageCategory, UrgencyLevel
from src.utils.logging import get_logger
from config.settings import get_settings
from src.agents.handoffs import AgentEnum, ContextObject

logger = get_logger()
settings = get_settings()

@dataclass
class AgentResponse:
    """Resposta de um agente especialista"""
    agent_name: str
    category: str
    content: str
    sources: List[str]
    confidence: float
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None

@dataclass
class SynthesizedResponse:
    """Resposta sintetizada final"""
    content: str
    sources: List[str]
    agents_consulted: List[str]
    confidence: float
    urgency: str
    category: str
    timestamp: datetime
    requires_human_confirmation: bool
    warning_messages: List[str]
    chain_of_thought: str
    category_prefix: str

class StratusOrchestratorAgent:
    """
    Stratus.IA Orchestrator Agent - Coordenador Central
    
    Baseado no prompt original do Stratus.IA, responsável por:
    - Coordenar execução de agentes especialistas
    - Sintetizar respostas de múltiplos agentes
    - Aplicar regras de qualidade e validação
    - Formatar resposta final conforme padrões Stratus.IA
    - Implementar regras de síntese exclusiva
    """
    
    def __init__(self):
        self.name = "StratusOrchestratorAgent"
        
        # Mapeamento de agentes disponíveis
        self.available_agents = {
            "weather_agent": "WeatherAgent",
            "regulatory_agent": "RegulatoryAgent", 
            "technical_agent": "TechnicalAgent",
            "operations_agent": "OperationsAgent",
            "education_agent": "EducationAgent",
            "communication_agent": "CommunicationAgent"
        }
        
        # Templates de resposta por categoria - baseados no prompt original
        self.response_templates = {
            MessageCategory.REGULATORY: {
                "prefix": "✈️ **REGULAMENTAÇÃO AERONÁUTICA**\n\n",
                "requires_confirmation": True,
                "citation_required": True,
                "specialist_rules": [
                    "Cite RBAC (número, seção, parágrafo), texto literal entre aspas, link e data",
                    "Não inventar; se não localizar, informe '⚠ Informação oficial não localizada'",
                    "Cláusula de Confirmação Humana ao fim"
                ]
            },
            MessageCategory.TECHNICAL: {
                "prefix": "📚 **AERONAVES E MANUAIS TÉCNICOS**\n\n",
                "requires_confirmation": True,
                "citation_required": True,
                "specialist_rules": [
                    "Dados de aeronave, sistemas, procedimentos de POH/AFM, QRH, MEL, service bulletins",
                    "Indique modelo, edição, seção e página; referencie RBAC e IS",
                    "Exemplo prático aplicado",
                    "Cláusula de Confirmação Humana"
                ]
            },
            MessageCategory.WEATHER: {
                "prefix": "🌦 **METEOROLOGIA E INFORMAÇÕES OPERACIONAIS**\n\n",
                "requires_confirmation": True,
                "citation_required": True,
                "specialist_rules": [
                    "METAR, TAF, SIGMET, trends via REDEMET/AISWEB/AIP MET",
                    "Códigos ICAO, hora Zulu de emissão e validade, trecho literal",
                    "Indique fontes e link, timestamp, cláusula de validação humana"
                ]
            },
            MessageCategory.GEOGRAPHIC: {
                "prefix": "🌐 **LOCALIZAÇÃO E ADAPTAÇÃO GEOGRÁFICA**\n\n",
                "requires_confirmation": True,
                "citation_required": True,
                "specialist_rules": [
                    "FIR, aeródromos, relevo, fronteiras",
                    "Cite código ICAO/FIR, seção AIP (GEN/ENR/AD), NOTAM/cartas, timestamp",
                    "Adapte altitudes, separações e restrições locais",
                    "Cláusula de Confirmação Humana"
                ]
            },
            MessageCategory.PERFORMANCE: {
                "prefix": "⚖️ **PESO, BALANCEAMENTO E PERFORMANCE**\n\n",
                "requires_confirmation": True,
                "citation_required": True,
                "specialist_rules": [
                    "Cálculos de peso, CG, performance de decolagem/pouso/cruzeiro conforme POH e RBAC",
                    "Modelo, revisão, seção, página; referencie RBAC e IS",
                    "Exemplo prático",
                    "Cláusula de Confirmação Humana"
                ]
            },
            MessageCategory.OPERATIONS: {
                "prefix": "🧭 **PLANEJAMENTO DE VOO OPERACIONAL**\n\n",
                "requires_confirmation": True,
                "citation_required": True,
                "specialist_rules": [
                    "Rota, altitude, combustível (trip + reserva + alternado + contingência), alternado",
                    "Cite RBAC, AIP ENR, ICAO Doc",
                    "Inclua notas sobre ETOPS, RVSM, PBN, meteorologia e NOTAM",
                    "Cláusula de Confirmação Humana"
                ]
            },
            MessageCategory.EDUCATION: {
                "prefix": "🎓 **EDUCAÇÃO E CARREIRA AERONÁUTICA**\n\n",
                "requires_confirmation": True,
                "citation_required": True,
                "specialist_rules": [
                    "Requisitos de licenças, horas de voo, exames, proficiência linguística",
                    "Cite RBAC 61/65, IS, Portal ANAC, data de emenda",
                    "Exemplo prático de aplicação",
                    "Cláusula de Confirmação Humana"
                ]
            },
            MessageCategory.COMMUNICATION: {
                "prefix": "📡 **COMUNICAÇÃO TÉCNICA E DIDÁTICA**\n\n",
                "requires_confirmation": True,
                "citation_required": False,
                "specialist_rules": [
                    "Definição de termos, siglas, jargões",
                    "Adapte ao nível do usuário (iniciante, intermediário, avançado)",
                    "Cite glossários ANAC, AIP GEN, ICAO",
                    "Inclua analogia ou exemplo",
                    "Cláusula de Confirmação Humana"
                ]
            },
            MessageCategory.SOCIAL: {
                "prefix": "🗣 **STRATUS.IA**\n\n",
                "requires_confirmation": False,
                "citation_required": False,
                "specialist_rules": [
                    "Mensagens sem conteúdo técnico (saudações, agradecimentos, bate-papo)",
                    "Resposta breve, simpática, mantendo personalidade do Renato",
                    "Evitar termos técnicos e não direcionar para especialistas",
                    "Encerre se não houver continuidade necessária"
                ]
            }
        }

        # handoff_manager.register_agent(AgentEnum.ORCHESTRATOR, self)

    async def execute_agents(self, classification: MessageClassification, 
                           message: str, user_id: str) -> List[AgentResponse]:
        """Executa agentes especialistas recomendados"""
        
        agent_responses = []
        
        # Para interação social, não executa agentes
        if classification.primary_category == MessageCategory.SOCIAL:
            social_response = AgentResponse(
                agent_name="orchestrator",
                category="social",
                content=self._generate_social_response(message),
                sources=[],
                confidence=1.0,
                timestamp=datetime.now(timezone.utc),
                success=True
            )
            return [social_response]
        
        # Executar agentes recomendados
        for agent_name in classification.recommended_agents:
            if agent_name in self.available_agents:
                try:
                    # TODO: Implementar chamada real para agentes quando estiverem prontos
                    # Por enquanto, simular resposta baseada no prompt original
                    response = await self._simulate_agent_call(
                        agent_name, message, classification, user_id
                    )
                    agent_responses.append(response)
                    
                except Exception as e:
                    error_response = AgentResponse(
                        agent_name=agent_name,
                        category=classification.primary_category.value,
                        content="",
                        sources=[],
                        confidence=0.0,
                        timestamp=datetime.now(timezone.utc),
                        success=False,
                        error_message=str(e)
                    )
                    agent_responses.append(error_response)
                    
                    logger.log_agent_action(
                        agent_name=self.name,
                        action="execute_agent",
                        message=f"Erro ao executar {agent_name}: {str(e)}",
                        user_id=user_id,
                        success=False,
                        additional_context={"agent": agent_name, "error": str(e)}
                    )
        
        return agent_responses

    async def _simulate_agent_call(self, agent_name: str, message: str, 
                                 classification: MessageClassification, 
                                 user_id: str) -> AgentResponse:
        """Simula chamada de agente baseada no prompt original"""
        
        # Simular delay de processamento
        await asyncio.sleep(0.1)
        
        # Conteúdo simulado baseado no tipo de agente e regras do prompt original
        simulated_content = {
            "weather_agent": "⚠ Informação meteorológica não disponível nas fontes oficiais consultadas (REDEMET, AISWEB, AIP MET). Recomenda-se consultar REDEMET ou AISWEB diretamente para dados METAR, TAF, SIGMET atualizados.",
            "regulatory_agent": "⚠ Informação regulatória não disponível nas fontes oficiais consultadas (RBAC, IS, ANAC). Recomenda-se consultar RBAC ou IS específico na fonte ANAC com número, seção, parágrafo e data de verificação.",
            "technical_agent": "⚠ Informação técnica não disponível nas fontes oficiais consultadas (POH/AFM, QRH, MEL, service bulletins). Recomenda-se consultar POH/AFM da aeronave específica com modelo, edição, seção e página.",
            "operations_agent": "⚠ Informação operacional não disponível nas fontes oficiais consultadas (AIP Brasil, RBAC, ICAO Doc). Recomenda-se consultar AIP ENR ou documentação operacional para planejamento de voo, rotas e procedimentos.",
            "education_agent": "⚠ Informação educacional não disponível nas fontes oficiais consultadas (RBAC 61/65, IS, Portal ANAC). Recomenda-se consultar Portal ANAC ou RBAC 61/65 para requisitos de licenças, horas de voo e exames.",
            "communication_agent": "⚠ Informação de comunicação não disponível nas fontes oficiais consultadas (AIP GEN, glossários ANAC/ICAO). Recomenda-se consultar AIP GEN ou glossários oficiais para definição de termos e fraseologia."
        }
        
        # Fontes simuladas baseadas no prompt original
        simulated_sources = {
            "weather_agent": ["REDEMET", "AISWEB", "AIP MET"],
            "regulatory_agent": ["RBAC", "IS", "Portal ANAC"],
            "technical_agent": ["POH/AFM", "QRH", "MEL", "Service Bulletins"],
            "operations_agent": ["AIP Brasil", "RBAC", "ICAO Doc"],
            "education_agent": ["RBAC 61/65", "IS", "Portal ANAC"],
            "communication_agent": ["AIP GEN", "Glossários ANAC/ICAO"]
        }
        
        return AgentResponse(
            agent_name=agent_name,
            category=classification.primary_category.value,
            content=simulated_content.get(agent_name, "Informação não disponível."),
            sources=simulated_sources.get(agent_name, ["Fonte não especificada"]),
            confidence=0.5,
            timestamp=datetime.now(timezone.utc),
            success=True
        )

    def _generate_social_response(self, message: str) -> str:
        """Gera resposta para interação social baseada no prompt original"""
        message_lower = message.lower()
        
        if any(greeting in message_lower for greeting in ['olá', 'oi', 'bom dia', 'boa tarde', 'boa noite']):
            return "Olá! Sou o Stratus.IA, seu assistente especializado em aviação civil brasileira. Como posso ajudá-lo hoje com suas dúvidas sobre regulamentação, meteorologia, aeronaves ou qualquer tema aeronáutico?"
        
        elif any(thanks in message_lower for thanks in ['obrigado', 'obrigada', 'valeu', 'muito obrigado']):
            return "De nada! Fico feliz em poder ajudar. Se tiver mais dúvidas sobre aviação, regulamentação ou qualquer tema aeronáutico, estarei aqui!"
        
        elif any(goodbye in message_lower for goodbye in ['tchau', 'até logo', 'até mais', 'adeus']):
            return "Até logo! Voe sempre com segurança. Estarei aqui quando precisar de informações sobre aviação!"
        
        elif any(question in message_lower for question in ['como vai', 'tudo bem', 'como está']):
            return "Estou funcionando perfeitamente e pronto para ajudar com suas dúvidas sobre aviação civil brasileira!"
        
        else:
            return "Olá! Sou o Stratus.IA. Se tiver alguma dúvida sobre aviação, regulamentação, meteorologia ou qualquer tema aeronáutico, ficarei feliz em ajudar!"

    def _validate_agent_responses(self, responses: List[AgentResponse]) -> List[str]:
        """Valida respostas dos agentes e retorna warnings"""
        warnings = []
        
        successful_responses = [r for r in responses if r.success]
        failed_responses = [r for r in responses if not r.success]
        
        if failed_responses:
            failed_agents = [r.agent_name for r in failed_responses]
            warnings.append(f"⚠ Falha na consulta aos agentes: {', '.join(failed_agents)}")
        
        if not successful_responses:
            warnings.append("⚠ Nenhum agente conseguiu fornecer informações válidas")
        
        # Verificar consistência de fontes
        all_sources = []
        for response in successful_responses:
            all_sources.extend(response.sources)
        
        if not all_sources:
            warnings.append("⚠ Nenhuma fonte oficial foi consultada")
        
        # Verificar se há conteúdo válido
        valid_content_responses = [r for r in successful_responses if r.content.strip() and not r.content.startswith("⚠")]
        if not valid_content_responses:
            warnings.append("⚠ Nenhuma informação válida foi obtida das fontes consultadas")
        
        return warnings

    def _synthesize_responses(self, responses: List[AgentResponse], 
                            classification: MessageClassification) -> str:
        """Sintetiza respostas de múltiplos agentes seguindo regras do prompt original"""
        
        successful_responses = [r for r in responses if r.success and r.content.strip()]
        
        # Regra de síntese exclusiva: se nenhum agente forneceu informação válida
        if not successful_responses:
            return "⚠ Informação não disponível nas fontes oficiais consultadas. Recomenda-se consultar a fonte original ou autoridade aeronáutica."
        
        # Para resposta social, retornar diretamente
        if classification.primary_category == MessageCategory.SOCIAL:
            return successful_responses[0].content
        
        # Filtrar respostas que não são apenas avisos
        valid_responses = [r for r in successful_responses if not r.content.startswith("⚠")]
        
        if not valid_responses:
            return "⚠ Informação não disponível nas fontes oficiais consultadas. Recomenda-se consultar a fonte original ou autoridade aeronáutica."
        
        # Para respostas técnicas, sintetizar seguindo regras do prompt original
        synthesized_content = ""
        
        if len(valid_responses) == 1:
            # Resposta única - usar diretamente
            synthesized_content = valid_responses[0].content
        else:
            # Múltiplas respostas - sintetizar conforme regras do prompt
            synthesized_content = "**INFORMAÇÕES CONSOLIDADAS DOS ESPECIALISTAS CONSULTADOS:**\n\n"
            
            for i, response in enumerate(valid_responses, 1):
                agent_display_name = response.agent_name.replace("_agent", "").title()
                synthesized_content += f"**{i}. {agent_display_name}:**\n"
                synthesized_content += f"{response.content}\n\n"
        
        return synthesized_content

    def _format_final_response(self, content: str, classification: MessageClassification,
                             responses: List[AgentResponse], warnings: List[str]) -> str:
        """Formata resposta final conforme padrões Stratus.IA e prompt original"""
        
        template = self.response_templates.get(classification.primary_category, {})
        prefix = template.get("prefix", "")
        requires_confirmation = template.get("requires_confirmation", False)
        citation_required = template.get("citation_required", False)
        
        # Construir resposta final
        final_response = prefix + content
        
        # Adicionar warnings se houver
        if warnings:
            final_response += "\n\n**⚠ AVISOS:**\n"
            for warning in warnings:
                final_response += f"• {warning}\n"
        
        # Adicionar fontes consultadas (sempre que citation_required)
        if citation_required:
            all_sources = []
            for response in responses:
                if response.success and response.sources:
                    all_sources.extend(response.sources)
            
            if all_sources:
                unique_sources = list(set(all_sources))
                final_response += "\n\n**📚 FONTES CONSULTADAS:**\n"
                for source in unique_sources:
                    final_response += f"• {source}\n"
        
        # Adicionar cláusula de confirmação humana se necessário
        if requires_confirmation and classification.primary_category != MessageCategory.SOCIAL:
            final_response += "\n\n**⚠ CLÁUSULA DE CONFIRMAÇÃO HUMANA:**\n"
            final_response += "Esta informação deve ser confirmada com fontes oficiais atualizadas antes de qualquer aplicação operacional. "
            final_response += "O Stratus.IA não substitui consulta direta às autoridades aeronáuticas competentes. "
            final_response += "Sempre verifique a data de emissão e validade das informações consultadas."
        
        return final_response

    async def orchestrate(self, message: str, classification: MessageClassification,
                         user_id: str = "system") -> SynthesizedResponse:
        """Orquestra execução completa e síntese de resposta"""
        
        start_time = datetime.now()
        
        logger.log_agent_action(
            agent_name=self.name,
            action="orchestrate_start",
            message=f"Iniciando orquestração para categoria {classification.primary_category.value}",
            user_id=user_id,
            success=True,
            additional_context={
                "category": classification.primary_category.value,
                "agents": classification.recommended_agents,
                "urgency": classification.urgency.value
            }
        )
        
        # Executar agentes
        agent_responses = await self.execute_agents(classification, message, user_id)
        
        # Validar respostas
        warnings = self._validate_agent_responses(agent_responses)
        
        # Sintetizar respostas seguindo regras do prompt original
        synthesized_content = self._synthesize_responses(agent_responses, classification)
        
        # Formatar resposta final
        final_content = self._format_final_response(
            synthesized_content, classification, agent_responses, warnings
        )
        
        # Calcular confiança média
        successful_responses = [r for r in agent_responses if r.success]
        avg_confidence = sum(r.confidence for r in successful_responses) / len(successful_responses) if successful_responses else 0.0
        
        # Coletar fontes
        all_sources = []
        for response in agent_responses:
            if response.success:
                all_sources.extend(response.sources)
        
        # Determinar se requer confirmação humana
        template = self.response_templates.get(classification.primary_category, {})
        requires_confirmation = template.get("requires_confirmation", False)
        
        synthesized_response = SynthesizedResponse(
            content=final_content,
            sources=list(set(all_sources)),
            agents_consulted=[r.agent_name for r in agent_responses if r.success],
            confidence=avg_confidence,
            urgency=classification.urgency.value,
            category=classification.primary_category.value,
            timestamp=datetime.now(timezone.utc),
            requires_human_confirmation=requires_confirmation,
            warning_messages=warnings,
            chain_of_thought=classification.chain_of_thought,
            category_prefix=template.get("prefix", "")
        )
        
        # Log final
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.log_agent_action(
            agent_name=self.name,
            action="orchestrate_complete",
            message=f"Orquestração concluída em {processing_time:.2f}s",
            user_id=user_id,
            success=True,
            additional_context={
                "processing_time_seconds": processing_time,
                "agents_executed": len(agent_responses),
                "successful_agents": len(successful_responses),
                "confidence": avg_confidence,
                "warnings_count": len(warnings),
                "requires_confirmation": requires_confirmation
            }
        )
        
        return synthesized_response

    async def process_with_handoffs(self, context: ContextObject) -> str:
        """Processa requisição usando sistema de handoffs"""
        try:
            # Determina agente alvo baseado na classificação
            target_agent = self._determine_target_agent(context)
            if target_agent == AgentEnum.ORCHESTRATOR:
                return await self.process_request(context)
            result = await handoff_manager.delegate(context, target_agent)
            if result.success:
                validation_result = await handoff_manager.validate(
                    result.context,
                    result.response,
                    {"require_sources": True, "approval_threshold": 0.7}
                )
                if validation_result.metadata.get("validation_approved", False):
                    return result.response
                else:
                    escalation_result = await handoff_manager.escalate(
                        context,
                        AgentEnum.ORCHESTRATOR,
                        "Resposta não passou na validação",
                        "Tentar agente alternativo ou reformular pergunta"
                    )
                    return f"⚠️ Resposta necessita revisão: {escalation_result.response}"
            else:
                escalation_result = await handoff_manager.escalate(
                    context,
                    AgentEnum.ORCHESTRATOR,
                    f"Falha na delegação: {result.error}",
                    "Verificar disponibilidade do agente ou tentar alternativo"
                )
                return f"❌ Erro no processamento: {escalation_result.response}"
        except Exception as e:
            self.logger.error(f"Erro no processamento com handoffs: {str(e)}")
            return f"❌ Erro interno: {str(e)}"

# Instância global do orchestrator
orchestrator_agent = StratusOrchestratorAgent() 