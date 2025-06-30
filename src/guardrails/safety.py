from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union, Callable
from enum import Enum
import asyncio
import logging
import re
import json
from datetime import datetime
from dataclasses import dataclass

# Imports específicos do OpenAI Agents SDK
from agents import (
    Agent,
    GuardrailFunctionOutput,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
    input_guardrail,
    output_guardrail,
)

class GuardrailType(Enum):
    SAFETY_VALIDATOR = "safety_validator"
    CONTENT_FILTER = "content_filter"
    HALLUCINATION_DETECTOR = "hallucination_detector"
    COMPLIANCE_CHECKER = "compliance_checker"
    AVIATION_SAFETY = "aviation_safety"
    REGULATORY_COMPLIANCE = "regulatory_compliance"
    PERFORMANCE_MONITOR = "performance_monitor"

class SafetyLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SAFE = "safe"

class ComplianceType(Enum):
    ANAC_RBAC = "anac_rbac"
    ICAO_ANNEX = "icao_annex"
    DECEA_ICA = "decea_ica"
    SAFETY_MANAGEMENT = "safety_management"

class SafetyValidationOutput(BaseModel):
    """Output do Safety Validator"""
    is_safety_critical: bool = Field(description="Se contém informações críticas de segurança")
    safety_level: SafetyLevel = Field(description="Nível de criticidade de segurança")
    safety_violations: List[str] = Field(default_factory=list, description="Violações de segurança identificadas")
    emergency_keywords: List[str] = Field(default_factory=list, description="Palavras-chave de emergência encontradas")
    reasoning: str = Field(description="Raciocínio da análise de segurança")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confiança na análise")

class ContentFilterOutput(BaseModel):
    """Output do Content Filter"""
    is_inappropriate: bool = Field(description="Se contém conteúdo inadequado")
    content_violations: List[str] = Field(default_factory=list, description="Tipos de violações encontradas")
    filtered_content: Optional[str] = Field(None, description="Conteúdo filtrado se aplicável")
    severity_score: float = Field(ge=0.0, le=1.0, description="Severidade do conteúdo inadequado")
    reasoning: str = Field(description="Raciocínio da filtragem")

class HallucinationDetectionOutput(BaseModel):
    """Output do Hallucination Detector"""
    is_hallucination: bool = Field(description="Se contém informações inventadas")
    hallucination_indicators: List[str] = Field(default_factory=list, description="Indicadores de alucinação")
    factual_accuracy_score: float = Field(ge=0.0, le=1.0, description="Score de precisão factual")
    sources_mentioned: List[str] = Field(default_factory=list, description="Fontes mencionadas na resposta")
    unsupported_claims: List[str] = Field(default_factory=list, description="Afirmações sem suporte")
    reasoning: str = Field(description="Raciocínio da detecção")

class ComplianceCheckOutput(BaseModel):
    """Output do Compliance Checker"""
    is_compliant: bool = Field(description="Se está em conformidade regulatória")
    compliance_violations: List[str] = Field(default_factory=list, description="Violações de compliance")
    regulatory_references: List[str] = Field(default_factory=list, description="Referências regulatórias citadas")
    compliance_score: float = Field(ge=0.0, le=1.0, description="Score de conformidade")
    missing_disclaimers: List[str] = Field(default_factory=list, description="Disclaimers obrigatórios ausentes")
    reasoning: str = Field(description="Raciocínio da verificação")

@dataclass
class GuardrailResult:
    """Resultado agregado de todos os guardrails"""
    results: Dict[str, GuardrailFunctionOutput]
    tripwires_triggered: List[str]
    execution_time: float
    overall_safe: bool
    error: Optional[str] = None

@dataclass
class GuardrailMetrics:
    """Métricas de performance dos guardrails"""
    total_checks: int = 0
    violations_detected: int = 0
    false_positives: int = 0
    avg_response_time: float = 0.0
    last_check: Optional[datetime] = None
    guardrail_type: GuardrailType = None

    def reset(self):
        self.total_checks = 0
        self.violations_detected = 0
        self.false_positives = 0
        self.avg_response_time = 0.0
        self.last_check = None

class AviationSafetyOutput(BaseModel):
    """Output do validador de segurança de aviação"""
    safety_violations: List[str] = Field(default_factory=list, description="Violações de segurança detectadas")
    severity_score: float = Field(ge=0.0, le=1.0, description="Severidade das violações de segurança")
    reasoning: str = Field(description="Raciocínio da análise de segurança")

class RegulatoryComplianceOutput(BaseModel):
    """Output do validador de conformidade regulatória"""
    compliance_violations: List[str] = Field(default_factory=list, description="Violações de conformidade detectadas")
    severity_score: float = Field(ge=0.0, le=1.0, description="Severidade das violações de conformidade")
    reasoning: str = Field(description="Raciocínio da análise de conformidade")

class PerformanceMonitorOutput(BaseModel):
    """Output do monitor de performance"""
    quality_score: float = Field(ge=0.0, le=1.0, description="Score de qualidade da resposta")
    performance_issues: List[str] = Field(default_factory=list, description="Problemas de performance detectados")
    reasoning: str = Field(description="Raciocínio da análise de performance")

class ICAOValidator:
    """Validador de códigos ICAO para aviação civil"""
    def __init__(self):
        self.logger = logging.getLogger("stratus.guardrails.icao")
        self.metrics = GuardrailMetrics(guardrail_type=GuardrailType.SAFETY_VALIDATOR)
        self.valid_icao_codes = [
            "SBSP", "SBGR", "SBRJ", "SBGL", "SBCF", "SBCT", "SBBR", "SBPA",
            "SBRF", "SBSV", "SBFZ", "SBMO", "SBCY", "SBKP", "SBVT", "SBGO",
            "SBCG", "SBFL", "SBMQ", "SBJP", "SBSL", "SBPV", "SBTE", "SBUL"
        ]

    async def validate_icao_codes(self, ctx, agent, input_data: str | list[str]) -> GuardrailFunctionOutput:
        """Valida se os códigos ICAO presentes no input são válidos"""
        start_time = datetime.now()
        try:
            if isinstance(input_data, str):
                text = input_data
            elif isinstance(input_data, list):
                text = " ".join(input_data)
            else:
                text = str(input_data)
            icao_pattern = r'\b[A-Z]{4}\b'
            icao_codes = re.findall(icao_pattern, text.upper())
            invalid_icao = [code for code in icao_codes if code not in self.valid_icao_codes]
            is_valid = len(invalid_icao) == 0
            execution_time = (datetime.now() - start_time).total_seconds()
            self.metrics.total_checks += 1
            if not is_valid:
                self.metrics.violations_detected += len(invalid_icao)
            if self.metrics.avg_response_time == 0:
                self.metrics.avg_response_time = execution_time
            else:
                self.metrics.avg_response_time = (
                    (self.metrics.avg_response_time * (self.metrics.total_checks - 1) + execution_time)
                    / self.metrics.total_checks
                )
            self.metrics.last_check = datetime.now()
            output = SafetyValidationOutput(
                is_safety_critical=not is_valid,
                safety_level=SafetyLevel.CRITICAL if not is_valid else SafetyLevel.SAFE,
                safety_violations=[f"Código ICAO inválido: {code}" for code in invalid_icao],
                emergency_keywords=[],
                reasoning="Validação de códigos ICAO.",
                confidence_score=1.0 if is_valid else 0.0
            )
            return GuardrailFunctionOutput(
                output_info=output,
                tripwire_triggered=not is_valid
            )
        except Exception as e:
            self.logger.error(f"Erro na validação ICAO: {str(e)}")
            output = SafetyValidationOutput(
                is_safety_critical=True,
                safety_level=SafetyLevel.CRITICAL,
                safety_violations=["Erro na validação de ICAO"],
                emergency_keywords=[],
                reasoning=f"Erro interno: {str(e)}",
                confidence_score=0.0
            )
            return GuardrailFunctionOutput(
                output_info=output,
                tripwire_triggered=True
            )

class SafetyValidator:
    """Validador de segurança operacional para aviação"""
    
    def __init__(self):
        self.logger = logging.getLogger("stratus.guardrails.safety")
        self.metrics = GuardrailMetrics(guardrail_type=GuardrailType.SAFETY_VALIDATOR)
        
        # Palavras-chave críticas de segurança
        self.emergency_keywords = [
            "emergência", "emergency", "mayday", "pan pan",
            "falha crítica", "critical failure", "engine failure",
            "perda de controle", "loss of control", "stall",
            "colisão", "collision", "tcas", "gpws",
            "fogo", "fire", "smoke", "fumaça",
            "despressurização", "depressurization",
            "pouso forçado", "emergency landing",
            "evacuação", "evacuation"
        ]
        
        # Palavras-chave de risco alto
        self.high_risk_keywords = [
            "turbulência severa", "severe turbulence",
            "gelo", "icing", "windshear",
            "baixa visibilidade", "low visibility",
            "combustível baixo", "low fuel",
            "sistema inoperante", "system inoperative",
            "limitação", "limitation", "restrição"
        ]
        
        # Códigos ICAO brasileiros válidos (exemplo)
        self.valid_icao_codes = [
            "SBSP", "SBGR", "SBRJ", "SBGL", "SBCF", "SBCT", "SBBR", "SBPA",
            "SBRF", "SBSV", "SBFZ", "SBMO", "SBCY", "SBKP", "SBVT", "SBGO",
            "SBCG", "SBFL", "SBMQ", "SBJP", "SBSL", "SBPV", "SBTE", "SBUL"
        ]
        
        # Agente especializado em segurança
        self.safety_agent = Agent(
            name="Safety Validator Agent",
            instructions="""Você é um especialista em segurança operacional de aviação.\n\nAnalise o conteúdo fornecido e identifique:\n1. Informações críticas de segurança de voo\n2. Situações de emergência ou risco\n3. Procedimentos de segurança mencionados\n4. Violações de segurança operacional\n5. Códigos ICAO e sua validade\n\nSeja extremamente rigoroso - em aviação, segurança é prioridade absoluta.\nClassifique o nível de criticidade e forneça raciocínio detalhado.\n\nNUNCA minimize riscos de segurança. Se há dúvida, classifique como crítico.""",
            output_type=SafetyValidationOutput,
        )
    
    async def validate_input_safety(
        self, 
        ctx: RunContextWrapper[None], 
        agent: Agent, 
        input_data: str | list[TResponseInputItem]
    ) -> GuardrailFunctionOutput:
        """Valida segurança do input do usuário"""
        start_time = datetime.now()
        self = ctx.guardrails.safety_validator if hasattr(ctx, 'guardrails') and hasattr(ctx.guardrails, 'safety_validator') else self
        try:
            input_text = self._extract_text_from_input(input_data)
            quick_safety_check = self._quick_safety_analysis(input_text)
            if quick_safety_check["is_emergency"]:
                self.logger.critical(
                    f"EMERGÊNCIA DETECTADA NO INPUT: {input_text[:100]}",
                    extra={"emergency_keywords": quick_safety_check["emergency_keywords"]}
                )
            safety_prompt = f"""Analise a segurança operacional desta mensagem de aviação:\n\nMENSAGEM: {input_text}\n\nIdentifique:\n- Situações de emergência ou risco\n- Códigos ICAO mencionados e sua validade\n- Procedimentos de segurança envolvidos\n- Nível de criticidade da situação\n- Violações de segurança operacional\n\nSeja rigoroso na análise de segurança."""
            result = await Runner.run(
                self.safety_agent, 
                safety_prompt, 
                context=ctx.context
            )
            safety_output = result.final_output
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(safety_output.is_safety_critical, execution_time)
            self.logger.info(
                f"Análise de segurança concluída",
                extra={
                    "safety_level": safety_output.safety_level.value,
                    "is_critical": safety_output.is_safety_critical,
                    "violations": safety_output.safety_violations,
                    "execution_time": execution_time
                }
            )
            tripwire_triggered = (
                safety_output.is_safety_critical or 
                safety_output.safety_level == SafetyLevel.CRITICAL or
                len(safety_output.safety_violations) > 0
            )
            return GuardrailFunctionOutput(
                output_info=safety_output,
                tripwire_triggered=tripwire_triggered,
            )
        except Exception as e:
            self.logger.error(f"Erro na validação de segurança: {str(e)}")
            return GuardrailFunctionOutput(
                output_info=SafetyValidationOutput(
                    is_safety_critical=True,
                    safety_level=SafetyLevel.CRITICAL,
                    safety_violations=["Erro na análise de segurança"],
                    emergency_keywords=[],
                    reasoning=f"Erro interno: {str(e)}",
                    confidence_score=0.0
                ),
                tripwire_triggered=True,
            )
    
    async def validate_output_safety(
        self, 
        ctx: RunContextWrapper, 
        agent: Agent, 
        output_data: Any
    ) -> GuardrailFunctionOutput:
        """Valida segurança do output do agente"""
        start_time = datetime.now()
        self = ctx.guardrails.safety_validator if hasattr(ctx, 'guardrails') and hasattr(ctx.guardrails, 'safety_validator') else self
        try:
            output_text = self._extract_text_from_output(output_data)
            safety_prompt = f"""Analise a segurança desta resposta de sistema de aviação:\n\nRESPOSTA: {output_text}\n\nVerifique:\n1. Se contém informações incorretas que podem comprometer segurança\n2. Se procedimentos de emergência estão corretos\n3. Se códigos ICAO estão válidos\n4. Se há disclaimers de segurança necessários\n5. Se informações críticas estão precisas\n\nCRÍTICO: Esta resposta será usada por profissionais de aviação. Qualquer erro pode ser fatal."""
            result = await Runner.run(
                self.safety_agent, 
                safety_prompt, 
                context=ctx.context
            )
            safety_output = result.final_output
            additional_checks = self._perform_additional_safety_checks(output_text)
            final_safety_output = self._combine_safety_results(safety_output, additional_checks)
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(final_safety_output.is_safety_critical, execution_time)
            tripwire_triggered = (
                final_safety_output.is_safety_critical or
                final_safety_output.safety_level in [SafetyLevel.CRITICAL, SafetyLevel.HIGH] or
                len(final_safety_output.safety_violations) > 2
            )
            if tripwire_triggered:
                self.logger.warning(
                    f"OUTPUT REPROVADO POR SEGURANÇA",
                    extra={
                        "safety_violations": final_safety_output.safety_violations,
                        "safety_level": final_safety_output.safety_level.value
                    }
                )
            return GuardrailFunctionOutput(
                output_info=final_safety_output,
                tripwire_triggered=tripwire_triggered,
            )
        except Exception as e:
            self.logger.error(f"Erro na validação de segurança do output: {str(e)}")
            return GuardrailFunctionOutput(
                output_info=SafetyValidationOutput(
                    is_safety_critical=True,
                    safety_level=SafetyLevel.CRITICAL,
                    safety_violations=["Erro na validação de output"],
                    emergency_keywords=[],
                    reasoning=f"Erro interno: {str(e)}",
                    confidence_score=0.0
                ),
                tripwire_triggered=True,
            )
    
    def _extract_text_from_input(self, input_data: str | list[TResponseInputItem]) -> str:
        if isinstance(input_data, str):
            return input_data
        elif isinstance(input_data, list):
            return " ".join([str(item) for item in input_data])
        else:
            return str(input_data)
    
    def _extract_text_from_output(self, output_data: Any) -> str:
        if hasattr(output_data, 'response'):
            return output_data.response
        elif hasattr(output_data, 'content'):
            return output_data.content
        elif isinstance(output_data, str):
            return output_data
        else:
            return str(output_data)
    
    def _quick_safety_analysis(self, text: str) -> Dict[str, Any]:
        text_lower = text.lower()
        emergency_found = [kw for kw in self.emergency_keywords if kw in text_lower]
        high_risk_found = [kw for kw in self.high_risk_keywords if kw in text_lower]
        icao_pattern = r'\b[A-Z]{4}\b'
        icao_codes = re.findall(icao_pattern, text.upper())
        invalid_icao = [code for code in icao_codes if code not in self.valid_icao_codes]
        return {
            "is_emergency": len(emergency_found) > 0,
            "emergency_keywords": emergency_found,
            "high_risk_keywords": high_risk_found,
            "icao_codes": icao_codes,
            "invalid_icao": invalid_icao
        }
    
    def _perform_additional_safety_checks(self, text: str) -> Dict[str, Any]:
        checks = {
            "missing_disclaimers": [],
            "procedural_errors": [],
            "data_inconsistencies": []
        }
        if any(kw in text.lower() for kw in ["metar", "taf", "notam"]):
            if "fonte:" not in text.lower() and "source:" not in text.lower():
                checks["missing_disclaimers"].append("Fonte não citada para dados meteorológicos")
        if any(kw in text.lower() for kw in self.emergency_keywords):
            if "consulte" not in text.lower() and "refer" not in text.lower():
                checks["procedural_errors"].append("Procedimento de emergência sem referência a manual")
        icao_codes = re.findall(r'\b[A-Z]{4}\b', text.upper())
        if len(set(icao_codes)) != len(icao_codes):
            checks["data_inconsistencies"].append("Códigos ICAO duplicados ou inconsistentes")
        return checks
    
    def _combine_safety_results(
        self, 
        agent_result: SafetyValidationOutput, 
        additional_checks: Dict[str, Any]
    ) -> SafetyValidationOutput:
        all_violations = agent_result.safety_violations.copy()
        all_violations.extend(additional_checks.get("missing_disclaimers", []))
        all_violations.extend(additional_checks.get("procedural_errors", []))
        all_violations.extend(additional_checks.get("data_inconsistencies", []))
        is_critical = agent_result.is_safety_critical or len(all_violations) > 2
        safety_level = agent_result.safety_level
        if len(all_violations) > 3:
            safety_level = SafetyLevel.CRITICAL
        elif len(all_violations) > 1:
            safety_level = SafetyLevel.HIGH
        return SafetyValidationOutput(
            is_safety_critical=is_critical,
            safety_level=safety_level,
            safety_violations=all_violations,
            emergency_keywords=agent_result.emergency_keywords,
            reasoning=f"{agent_result.reasoning}\n\nVerificações adicionais: {additional_checks}",
            confidence_score=max(0.0, agent_result.confidence_score - (len(all_violations) * 0.1))
        )
    
    def _update_metrics(self, violation_detected: bool, execution_time: float):
        self.metrics.total_checks += 1
        if violation_detected:
            self.metrics.violations_detected += 1
        if self.metrics.avg_response_time == 0:
            self.metrics.avg_response_time = execution_time
        else:
            self.metrics.avg_response_time = (
                (self.metrics.avg_response_time * (self.metrics.total_checks - 1) + execution_time) 
                / self.metrics.total_checks
            )
        self.metrics.last_check = datetime.now()

class ContentFilter:
    """Filtro de conteúdo inadequado para ambiente profissional"""
    
    def __init__(self):
        self.logger = logging.getLogger("stratus.guardrails.content")
        self.metrics = GuardrailMetrics(guardrail_type=GuardrailType.CONTENT_FILTER)
        
        # Categorias de conteúdo inadequado
        self.inappropriate_categories = {
            "profanity": [
                "palavrão", "xingamento", "obscenidade",
                # Lista seria mais extensa em implementação real
            ],
            "personal_attacks": [
                "idiota", "burro", "incompetente", "imbecil"
            ],
            "off_topic": [
                "futebol", "política", "religião", "fofoca",
                "receita", "piada", "meme"
            ],
            "inappropriate_requests": [
                "homework", "lição de casa", "trabalho escolar",
                "dissertação", "tese", "artigo acadêmico"
            ]
        }
        
        # Agente filtro de conteúdo
        self.content_agent = Agent(
            name="Content Filter Agent",
            instructions="""Você é um filtro de conteúdo para sistema profissional de aviação.\n\nAnalise o conteúdo e identifique:\n1. Linguagem inadequada ou ofensiva\n2. Conteúdo fora do escopo de aviação\n3. Solicitações inapropriadas\n4. Ataques pessoais ou linguagem hostil\n5. Conteúdo que não é profissional\n\nEste é um ambiente profissional de aviação. Mantenha padrões altos.\nSeja rigoroso mas justo na análise.""",
            output_type=ContentFilterOutput,
        )
    
    async def filter_input_content(
        self, 
        ctx: RunContextWrapper[None], 
        agent: Agent, 
        input_data: str | list[TResponseInputItem]
    ) -> GuardrailFunctionOutput:
        """Filtra conteúdo inadequado no input"""
        start_time = datetime.now()
        self = ctx.guardrails.content_filter if hasattr(ctx, 'guardrails') and hasattr(ctx.guardrails, 'content_filter') else self
        try:
            input_text = self._extract_text_from_input(input_data)
            quick_filter = self._quick_content_analysis(input_text)
            filter_prompt = f"""Analise este conteúdo para sistema profissional de aviação:\n\nCONTEÚDO: {input_text}\n\nVerifique se contém:\n- Linguagem inadequada ou ofensiva\n- Conteúdo fora do escopo de aviação\n- Solicitações inapropriadas (lição de casa, etc.)\n- Ataques pessoais\n- Qualquer coisa não profissional\n\nClassifique a severidade e forneça raciocínio."""
            result = await Runner.run(
                self.content_agent, 
                filter_prompt, 
                context=ctx.context
            )
            filter_output = result.final_output
            final_output = self._combine_filter_results(filter_output, quick_filter)
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(final_output.is_inappropriate, execution_time)
            tripwire_triggered = (
                final_output.is_inappropriate or
                final_output.severity_score > 0.7 or
                len(final_output.content_violations) > 0
            )
            if tripwire_triggered:
                self.logger.warning(
                    f"CONTEÚDO INADEQUADO DETECTADO",
                    extra={
                        "violations": final_output.content_violations,
                        "severity": final_output.severity_score
                    }
                )
            return GuardrailFunctionOutput(
                output_info=final_output,
                tripwire_triggered=tripwire_triggered,
            )
        except Exception as e:
            self.logger.error(f"Erro no filtro de conteúdo: {str(e)}")
            return GuardrailFunctionOutput(
                output_info=ContentFilterOutput(
                    is_inappropriate=True,
                    content_violations=["Erro na análise de conteúdo"],
                    severity_score=1.0,
                    reasoning=f"Erro interno: {str(e)}"
                ),
                tripwire_triggered=True,
            )
    
    async def filter_output_content(
        self, 
        ctx: RunContextWrapper, 
        agent: Agent, 
        output_data: Any
    ) -> GuardrailFunctionOutput:
        """Filtra conteúdo inadequado no output"""
        start_time = datetime.now()
        self = ctx.guardrails.content_filter if hasattr(ctx, 'guardrails') and hasattr(ctx.guardrails, 'content_filter') else self
        try:
            output_text = self._extract_text_from_output(output_data)
            filter_prompt = f"""Analise se esta resposta é apropriada para sistema profissional de aviação:\n\nRESPOSTA: {output_text}\n\nVerifique:\n1. Linguagem profissional e adequada\n2. Conteúdo relevante para aviação\n3. Ausência de informações pessoais inadequadas\n4. Tom respeitoso e técnico\n5. Conformidade com padrões profissionais\n\nEsta resposta será vista por profissionais de aviação."""
            result = await Runner.run(
                self.content_agent, 
                filter_prompt, 
                context=ctx.context
            )
            filter_output = result.final_output
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(filter_output.is_inappropriate, execution_time)
            tripwire_triggered = (
                filter_output.is_inappropriate or
                filter_output.severity_score > 0.5
            )
            return GuardrailFunctionOutput(
                output_info=filter_output,
                tripwire_triggered=tripwire_triggered,
            )
        except Exception as e:
            self.logger.error(f"Erro no filtro de output: {str(e)}")
            return GuardrailFunctionOutput(
                output_info=ContentFilterOutput(
                    is_inappropriate=True,
                    content_violations=["Erro na análise de output"],
                    severity_score=1.0,
                    reasoning=f"Erro interno: {str(e)}"
                ),
                tripwire_triggered=True,
            )
    
    def _extract_text_from_input(self, input_data: str | list[TResponseInputItem]) -> str:
        if isinstance(input_data, str):
            return input_data
        elif isinstance(input_data, list):
            return " ".join([str(item) for item in input_data])
        else:
            return str(input_data)
    
    def _extract_text_from_output(self, output_data: Any) -> str:
        if hasattr(output_data, 'response'):
            return output_data.response
        elif hasattr(output_data, 'content'):
            return output_data.content
        elif isinstance(output_data, str):
            return output_data
        else:
            return str(output_data)
    
    def _quick_content_analysis(self, text: str) -> Dict[str, Any]:
        text_lower = text.lower()
        violations = []
        for category, keywords in self.inappropriate_categories.items():
            found_keywords = [kw for kw in keywords if kw in text_lower]
            if found_keywords:
                violations.append({
                    "category": category,
                    "keywords": found_keywords
                })
        return {
            "violations": violations,
            "severity": len(violations) / len(self.inappropriate_categories)
        }
    
    def _combine_filter_results(
        self, 
        agent_result: ContentFilterOutput, 
        quick_analysis: Dict[str, Any]
    ) -> ContentFilterOutput:
        all_violations = agent_result.content_violations.copy()
        for violation in quick_analysis["violations"]:
            all_violations.append(f"{violation['category']}: {', '.join(violation['keywords'])}")
        max_severity = max(agent_result.severity_score, quick_analysis["severity"])
        return ContentFilterOutput(
            is_inappropriate=agent_result.is_inappropriate or len(all_violations) > 0,
            content_violations=all_violations,
            filtered_content=agent_result.filtered_content,
            severity_score=max_severity,
            reasoning=f"{agent_result.reasoning}\n\nAnálise rápida: {quick_analysis}"
        )
    
    def _update_metrics(self, violation_detected: bool, execution_time: float):
        self.metrics.total_checks += 1
        if violation_detected:
            self.metrics.violations_detected += 1
        if self.metrics.avg_response_time == 0:
            self.metrics.avg_response_time = execution_time
        else:
            self.metrics.avg_response_time = (
                (self.metrics.avg_response_time * (self.metrics.total_checks - 1) + execution_time) 
                / self.metrics.total_checks
            )
        self.metrics.last_check = datetime.now() 

class AviationSafety:
    """Validador de segurança de aviação"""
    
    def __init__(self):
        self.logger = logging.getLogger("stratus.guardrails.aviation")
        self.metrics = GuardrailMetrics(guardrail_type=GuardrailType.AVIATION_SAFETY)
        
        # Agente de segurança de aviação
        self.safety_agent = Agent(
            name="Aviation Safety Agent",
            instructions="""Você é um especialista em segurança de aviação.\n\nAnalise conteúdo relacionado a:\n1. Procedimentos de segurança\n2. Regulamentos de voo\n3. Emergências aeronáuticas\n4. Manutenção de aeronaves\n5. Operações de voo\n\nIdentifique:\n- Informações incorretas ou perigosas\n- Procedimentos inadequados\n- Violações de segurança\n- Recomendações inseguras\n\nSempre priorize a segurança acima de tudo.""",
            output_type=AviationSafetyOutput,
        )
    
    async def check_aviation_safety(
        self, 
        ctx: RunContextWrapper[None], 
        agent: Agent, 
        input_data: str | list[TResponseInputItem]
    ) -> GuardrailFunctionOutput:
        """Verifica segurança de aviação no input"""
        start_time = datetime.now()
        try:
            input_text = self._extract_text(input_data)
            safety_prompt = f"""Analise este conteúdo para segurança de aviação:\n\nCONTEÚDO: {input_text}\n\nVerifique se contém:\n- Procedimentos de segurança incorretos\n- Informações perigosas sobre voo\n- Violações de regulamentos\n- Recomendações inseguras\n- Qualquer coisa que possa comprometer a segurança\n\nClassifique a severidade e forneça raciocínio."""
            result = await Runner.run(
                self.safety_agent, 
                safety_prompt, 
                context=ctx.context
            )
            safety_output = result.final_output
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(safety_output.safety_violations, execution_time)
            tripwire_triggered = (
                safety_output.safety_violations or
                safety_output.severity_score > 0.6
            )
            return GuardrailFunctionOutput(
                output_info=safety_output,
                tripwire_triggered=tripwire_triggered,
            )
        except Exception as e:
            self.logger.error(f"Erro na verificação de segurança: {str(e)}")
            return GuardrailFunctionOutput(
                output_info=AviationSafetyOutput(
                    safety_violations=["Erro na análise de segurança"],
                    severity_score=1.0,
                    reasoning=f"Erro interno: {str(e)}"
                ),
                tripwire_triggered=True,
            )
    
    async def validate_aviation_safety(
        self, 
        ctx: RunContextWrapper, 
        agent: Agent, 
        output_data: Any
    ) -> GuardrailFunctionOutput:
        """Valida segurança de aviação no output"""
        start_time = datetime.now()
        try:
            output_text = self._extract_text(output_data)
            safety_prompt = f"""Valide se esta resposta é segura para aviação:\n\nRESPOSTA: {output_text}\n\nVerifique:\n1. Procedimentos de segurança corretos\n2. Informações precisas sobre voo\n3. Conformidade com regulamentos\n4. Recomendações seguras\n5. Ausência de informações perigosas\n\nEsta resposta será usada por profissionais de aviação."""
            result = await Runner.run(
                self.safety_agent, 
                safety_prompt, 
                context=ctx.context
            )
            safety_output = result.final_output
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(safety_output.safety_violations, execution_time)
            tripwire_triggered = (
                safety_output.safety_violations or
                safety_output.severity_score > 0.5
            )
            return GuardrailFunctionOutput(
                output_info=safety_output,
                tripwire_triggered=tripwire_triggered,
            )
        except Exception as e:
            self.logger.error(f"Erro na validação de segurança: {str(e)}")
            return GuardrailFunctionOutput(
                output_info=AviationSafetyOutput(
                    safety_violations=["Erro na validação de segurança"],
                    severity_score=1.0,
                    reasoning=f"Erro interno: {str(e)}"
                ),
                tripwire_triggered=True,
            )
    
    def _extract_text(self, data: Any) -> str:
        if isinstance(data, str):
            return data
        elif isinstance(data, list):
            return " ".join([str(item) for item in data])
        else:
            return str(data)
    
    def _update_metrics(self, violations: List[str], execution_time: float):
        self.metrics.total_checks += 1
        if violations:
            self.metrics.violations_detected += len(violations)
        if self.metrics.avg_response_time == 0:
            self.metrics.avg_response_time = execution_time
        else:
            self.metrics.avg_response_time = (
                (self.metrics.avg_response_time * (self.metrics.total_checks - 1) + execution_time) 
                / self.metrics.total_checks
            )
        self.metrics.last_check = datetime.now()

class RegulatoryCompliance:
    """Validador de conformidade regulatória"""
    
    def __init__(self):
        self.logger = logging.getLogger("stratus.guardrails.compliance")
        self.metrics = GuardrailMetrics(guardrail_type=GuardrailType.REGULATORY_COMPLIANCE)
        
        # Agente de conformidade
        self.compliance_agent = Agent(
            name="Regulatory Compliance Agent",
            instructions="""Você é um especialista em conformidade regulatória de aviação.\n\nAnalise conformidade com:\n1. Regulamentos ANAC\n2. Normas ICAO\n3. Procedimentos operacionais\n4. Requisitos legais\n5. Políticas da empresa\n\nIdentifique:\n- Violações regulatórias\n- Não conformidades\n- Procedimentos inadequados\n- Falhas de compliance\n\nMantenha padrões rigorosos de conformidade.""",
            output_type=RegulatoryComplianceOutput,
        )
    
    async def check_compliance(
        self, 
        ctx: RunContextWrapper[None], 
        agent: Agent, 
        input_data: str | list[TResponseInputItem]
    ) -> GuardrailFunctionOutput:
        """Verifica conformidade no input"""
        start_time = datetime.now()
        try:
            input_text = self._extract_text(input_data)
            compliance_prompt = f"""Analise conformidade regulatória:\n\nCONTEÚDO: {input_text}\n\nVerifique:\n- Violações de regulamentos ANAC\n- Não conformidades com normas ICAO\n- Procedimentos inadequados\n- Falhas de compliance\n- Requisitos legais não atendidos\n\nClassifique a severidade e forneça raciocínio."""
            result = await Runner.run(
                self.compliance_agent, 
                compliance_prompt, 
                context=ctx.context
            )
            compliance_output = result.final_output
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(compliance_output.compliance_violations, execution_time)
            tripwire_triggered = (
                compliance_output.compliance_violations or
                compliance_output.severity_score > 0.6
            )
            return GuardrailFunctionOutput(
                output_info=compliance_output,
                tripwire_triggered=tripwire_triggered,
            )
        except Exception as e:
            self.logger.error(f"Erro na verificação de conformidade: {str(e)}")
            return GuardrailFunctionOutput(
                output_info=RegulatoryComplianceOutput(
                    compliance_violations=["Erro na análise de conformidade"],
                    severity_score=1.0,
                    reasoning=f"Erro interno: {str(e)}"
                ),
                tripwire_triggered=True,
            )
    
    async def validate_compliance(
        self, 
        ctx: RunContextWrapper, 
        agent: Agent, 
        output_data: Any
    ) -> GuardrailFunctionOutput:
        """Valida conformidade no output"""
        start_time = datetime.now()
        try:
            output_text = self._extract_text(output_data)
            compliance_prompt = f"""Valide conformidade regulatória:\n\nRESPOSTA: {output_text}\n\nVerifique:\n1. Conformidade com regulamentos ANAC\n2. Adequação às normas ICAO\n3. Procedimentos corretos\n4. Compliance adequado\n5. Requisitos legais atendidos\n\nEsta resposta deve estar em conformidade total."""
            result = await Runner.run(
                self.compliance_agent, 
                compliance_prompt, 
                context=ctx.context
            )
            compliance_output = result.final_output
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(compliance_output.compliance_violations, execution_time)
            tripwire_triggered = (
                compliance_output.compliance_violations or
                compliance_output.severity_score > 0.5
            )
            return GuardrailFunctionOutput(
                output_info=compliance_output,
                tripwire_triggered=tripwire_triggered,
            )
        except Exception as e:
            self.logger.error(f"Erro na validação de conformidade: {str(e)}")
            return GuardrailFunctionOutput(
                output_info=RegulatoryComplianceOutput(
                    compliance_violations=["Erro na validação de conformidade"],
                    severity_score=1.0,
                    reasoning=f"Erro interno: {str(e)}"
                ),
                tripwire_triggered=True,
            )
    
    def _extract_text(self, data: Any) -> str:
        if isinstance(data, str):
            return data
        elif isinstance(data, list):
            return " ".join([str(item) for item in data])
        else:
            return str(data)
    
    def _update_metrics(self, violations: List[str], execution_time: float):
        self.metrics.total_checks += 1
        if violations:
            self.metrics.violations_detected += len(violations)
        if self.metrics.avg_response_time == 0:
            self.metrics.avg_response_time = execution_time
        else:
            self.metrics.avg_response_time = (
                (self.metrics.avg_response_time * (self.metrics.total_checks - 1) + execution_time) 
                / self.metrics.total_checks
            )
        self.metrics.last_check = datetime.now()

class PerformanceMonitor:
    """Monitor de performance e qualidade"""
    
    def __init__(self):
        self.logger = logging.getLogger("stratus.guardrails.performance")
        self.metrics = GuardrailMetrics(guardrail_type=GuardrailType.PERFORMANCE_MONITOR)
        
        # Agente de performance
        self.performance_agent = Agent(
            name="Performance Monitor Agent",
            instructions="""Você é um monitor de performance para sistema de IA.\n\nAnalise:\n1. Qualidade da resposta\n2. Precisão das informações\n3. Relevância do conteúdo\n4. Estrutura e clareza\n5. Adequação ao contexto\n\nIdentifique:\n- Respostas de baixa qualidade\n- Informações imprecisas\n- Conteúdo irrelevante\n- Estrutura inadequada\n- Falhas de performance\n\nMantenha padrões altos de qualidade.""",
            output_type=PerformanceMonitorOutput,
        )
    
    async def monitor_performance(
        self, 
        ctx: RunContextWrapper, 
        agent: Agent, 
        output_data: Any
    ) -> GuardrailFunctionOutput:
        """Monitora performance do output"""
        start_time = datetime.now()
        try:
            output_text = self._extract_text(output_data)
            performance_prompt = f"""Analise performance e qualidade:\n\nRESPOSTA: {output_text}\n\nAvalie:\n1. Qualidade geral da resposta\n2. Precisão das informações\n3. Relevância para o contexto\n4. Estrutura e clareza\n5. Adequação ao usuário\n\nClassifique a qualidade e identifique problemas."""
            result = await Runner.run(
                self.performance_agent, 
                performance_prompt, 
                context=ctx.context
            )
            performance_output = result.final_output
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(performance_output.quality_score, execution_time)
            tripwire_triggered = (
                performance_output.quality_score < 0.6 or
                performance_output.performance_issues
            )
            return GuardrailFunctionOutput(
                output_info=performance_output,
                tripwire_triggered=tripwire_triggered,
            )
        except Exception as e:
            self.logger.error(f"Erro no monitoramento de performance: {str(e)}")
            return GuardrailFunctionOutput(
                output_info=PerformanceMonitorOutput(
                    quality_score=0.0,
                    performance_issues=["Erro no monitoramento"],
                    reasoning=f"Erro interno: {str(e)}"
                ),
                tripwire_triggered=True,
            )
    
    def _extract_text(self, data: Any) -> str:
        if isinstance(data, str):
            return data
        elif hasattr(data, 'response'):
            return data.response
        elif hasattr(data, 'content'):
            return data.content
        else:
            return str(data)
    
    def _update_metrics(self, quality_score: float, execution_time: float):
        self.metrics.total_checks += 1
        if quality_score < 0.6:
            self.metrics.violations_detected += 1
        if self.metrics.avg_response_time == 0:
            self.metrics.avg_response_time = execution_time
        else:
            self.metrics.avg_response_time = (
                (self.metrics.avg_response_time * (self.metrics.total_checks - 1) + execution_time) 
                / self.metrics.total_checks
            )
        self.metrics.last_check = datetime.now()

class GuardrailManager:
    """Gerenciador central de todos os guardrails de segurança"""
    
    def __init__(self):
        self.logger = logging.getLogger("stratus.guardrails.manager")
        
        # Inicializa todos os guardrails
        self.icao_validator = ICAOValidator()
        self.content_filter = ContentFilter()
        self.aviation_safety = AviationSafety()
        self.regulatory_compliance = RegulatoryCompliance()
        self.performance_monitor = PerformanceMonitor()
        
        # Configurações
        self.enabled_guardrails = {
            "icao_validation": True,
            "content_filter": True,
            "aviation_safety": True,
            "regulatory_compliance": True,
            "performance_monitor": True
        }
        
        # Métricas agregadas
        self.aggregate_metrics = {
            "total_checks": 0,
            "total_violations": 0,
            "total_tripwires": 0,
            "avg_response_time": 0.0,
            "last_check": None
        }
    
    async def run_input_guardrails(
        self, 
        ctx: RunContextWrapper[None], 
        agent: Agent, 
        input_data: str | list[TResponseInputItem]
    ) -> GuardrailResult:
        """Executa todos os guardrails de input"""
        start_time = datetime.now()
        self.logger.info("Executando guardrails de input")
        
        results = {}
        tripwires_triggered = []
        
        try:
            # ICAO Validation
            if self.enabled_guardrails["icao_validation"]:
                icao_result = await self.icao_validator.validate_icao_codes(
                    ctx, agent, input_data
                )
                results["icao_validation"] = icao_result
                if icao_result.tripwire_triggered:
                    tripwires_triggered.append("icao_validation")
            
            # Content Filter
            if self.enabled_guardrails["content_filter"]:
                content_result = await self.content_filter.filter_input_content(
                    ctx, agent, input_data
                )
                results["content_filter"] = content_result
                if content_result.tripwire_triggered:
                    tripwires_triggered.append("content_filter")
            
            # Aviation Safety
            if self.enabled_guardrails["aviation_safety"]:
                safety_result = await self.aviation_safety.check_aviation_safety(
                    ctx, agent, input_data
                )
                results["aviation_safety"] = safety_result
                if safety_result.tripwire_triggered:
                    tripwires_triggered.append("aviation_safety")
            
            # Regulatory Compliance
            if self.enabled_guardrails["regulatory_compliance"]:
                compliance_result = await self.regulatory_compliance.check_compliance(
                    ctx, agent, input_data
                )
                results["regulatory_compliance"] = compliance_result
                if compliance_result.tripwire_triggered:
                    tripwires_triggered.append("regulatory_compliance")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_aggregate_metrics(results, execution_time)
            
            # Log resultados
            if tripwires_triggered:
                self.logger.warning(
                    f"GUARDRAILS TRIGGERED: {', '.join(tripwires_triggered)}",
                    extra={
                        "tripwires": tripwires_triggered,
                        "execution_time": execution_time,
                        "results": {k: v.tripwire_triggered for k, v in results.items()}
                    }
                )
            else:
                self.logger.info(
                    "Todos os guardrails de input passaram",
                    extra={"execution_time": execution_time}
                )
            
            return GuardrailResult(
                results=results,
                tripwires_triggered=tripwires_triggered,
                execution_time=execution_time,
                overall_safe=len(tripwires_triggered) == 0
            )
            
        except Exception as e:
            self.logger.error(f"Erro na execução dos guardrails de input: {str(e)}")
            return GuardrailResult(
                results={},
                tripwires_triggered=["error"],
                execution_time=(datetime.now() - start_time).total_seconds(),
                overall_safe=False,
                error=str(e)
            )
    
    async def run_output_guardrails(
        self, 
        ctx: RunContextWrapper, 
        agent: Agent, 
        output_data: Any
    ) -> GuardrailResult:
        """Executa todos os guardrails de output"""
        start_time = datetime.now()
        self.logger.info("Executando guardrails de output")
        
        results = {}
        tripwires_triggered = []
        
        try:
            # Content Filter
            if self.enabled_guardrails["content_filter"]:
                content_result = await self.content_filter.filter_output_content(
                    ctx, agent, output_data
                )
                results["content_filter"] = content_result
                if content_result.tripwire_triggered:
                    tripwires_triggered.append("content_filter")
            
            # Aviation Safety
            if self.enabled_guardrails["aviation_safety"]:
                safety_result = await self.aviation_safety.validate_aviation_safety(
                    ctx, agent, output_data
                )
                results["aviation_safety"] = safety_result
                if safety_result.tripwire_triggered:
                    tripwires_triggered.append("aviation_safety")
            
            # Regulatory Compliance
            if self.enabled_guardrails["regulatory_compliance"]:
                compliance_result = await self.regulatory_compliance.validate_compliance(
                    ctx, agent, output_data
                )
                results["regulatory_compliance"] = compliance_result
                if compliance_result.tripwire_triggered:
                    tripwires_triggered.append("regulatory_compliance")
            
            # Performance Monitor
            if self.enabled_guardrails["performance_monitor"]:
                performance_result = await self.performance_monitor.monitor_performance(
                    ctx, agent, output_data
                )
                results["performance_monitor"] = performance_result
                if performance_result.tripwire_triggered:
                    tripwires_triggered.append("performance_monitor")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_aggregate_metrics(results, execution_time)
            
            # Log resultados
            if tripwires_triggered:
                self.logger.warning(
                    f"OUTPUT GUARDRAILS TRIGGERED: {', '.join(tripwires_triggered)}",
                    extra={
                        "tripwires": tripwires_triggered,
                        "execution_time": execution_time,
                        "results": {k: v.tripwire_triggered for k, v in results.items()}
                    }
                )
            else:
                self.logger.info(
                    "Todos os guardrails de output passaram",
                    extra={"execution_time": execution_time}
                )
            
            return GuardrailResult(
                results=results,
                tripwires_triggered=tripwires_triggered,
                execution_time=execution_time,
                overall_safe=len(tripwires_triggered) == 0
            )
            
        except Exception as e:
            self.logger.error(f"Erro na execução dos guardrails de output: {str(e)}")
            return GuardrailResult(
                results={},
                tripwires_triggered=["error"],
                execution_time=(datetime.now() - start_time).total_seconds(),
                overall_safe=False,
                error=str(e)
            )
    
    def enable_guardrail(self, guardrail_name: str):
        """Habilita um guardrail específico"""
        if guardrail_name in self.enabled_guardrails:
            self.enabled_guardrails[guardrail_name] = True
            self.logger.info(f"Guardrail {guardrail_name} habilitado")
        else:
            self.logger.warning(f"Guardrail {guardrail_name} não encontrado")
    
    def disable_guardrail(self, guardrail_name: str):
        """Desabilita um guardrail específico"""
        if guardrail_name in self.enabled_guardrails:
            self.enabled_guardrails[guardrail_name] = False
            self.logger.info(f"Guardrail {guardrail_name} desabilitado")
        else:
            self.logger.warning(f"Guardrail {guardrail_name} não encontrado")
    
    def get_guardrail_status(self) -> Dict[str, bool]:
        """Retorna status de todos os guardrails"""
        return self.enabled_guardrails.copy()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas agregadas de todos os guardrails"""
        individual_metrics = {
            "icao_validator": self.icao_validator.metrics.__dict__,
            "content_filter": self.content_filter.metrics.__dict__,
            "aviation_safety": self.aviation_safety.metrics.__dict__,
            "regulatory_compliance": self.regulatory_compliance.metrics.__dict__,
            "performance_monitor": self.performance_monitor.metrics.__dict__
        }
        
        return {
            "aggregate": self.aggregate_metrics,
            "individual": individual_metrics,
            "enabled_guardrails": self.enabled_guardrails
        }
    
    def reset_metrics(self):
        """Reseta todas as métricas"""
        self.icao_validator.metrics.reset()
        self.content_filter.metrics.reset()
        self.aviation_safety.metrics.reset()
        self.regulatory_compliance.metrics.reset()
        self.performance_monitor.metrics.reset()
        
        self.aggregate_metrics = {
            "total_checks": 0,
            "total_violations": 0,
            "total_tripwires": 0,
            "avg_response_time": 0.0,
            "last_check": None
        }
        
        self.logger.info("Todas as métricas foram resetadas")
    
    def _update_aggregate_metrics(self, results: Dict[str, GuardrailFunctionOutput], execution_time: float):
        """Atualiza métricas agregadas"""
        self.aggregate_metrics["total_checks"] += 1
        self.aggregate_metrics["last_check"] = datetime.now()
        
        total_violations = 0
        total_tripwires = 0
        
        for result in results.values():
            if result.tripwire_triggered:
                total_tripwires += 1
            # Conta violações baseado no tipo de output
            if hasattr(result.output_info, 'violations_detected'):
                total_violations += result.output_info.violations_detected
            elif hasattr(result.output_info, 'content_violations'):
                total_violations += len(result.output_info.content_violations)
        
        self.aggregate_metrics["total_violations"] += total_violations
        self.aggregate_metrics["total_tripwires"] += total_tripwires
        
        # Atualiza tempo médio de resposta
        if self.aggregate_metrics["avg_response_time"] == 0:
            self.aggregate_metrics["avg_response_time"] = execution_time
        else:
            self.aggregate_metrics["avg_response_time"] = (
                (self.aggregate_metrics["avg_response_time"] * (self.aggregate_metrics["total_checks"] - 1) + execution_time)
                / self.aggregate_metrics["total_checks"]
            ) 