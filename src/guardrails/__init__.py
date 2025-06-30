"""
Sistema de Guardrails de Segurança para Stratus.IA

Este módulo implementa um sistema completo de guardrails para garantir
segurança, conformidade e qualidade no sistema de IA para aviação civil.

Componentes:
- SafetyValidator: Validação de códigos ICAO e segurança básica
- ContentFilter: Filtro de conteúdo inadequado
- AviationSafety: Validação de segurança de aviação
- RegulatoryCompliance: Conformidade regulatória
- PerformanceMonitor: Monitoramento de performance
- GuardrailManager: Gerenciador central de todos os guardrails

Características:
- Validação rigorosa de códigos ICAO
- Filtro de conteúdo inadequado para ambiente profissional
- Verificação de segurança de aviação
- Conformidade com regulamentos ANAC/ICAO
- Monitoramento de performance e qualidade
- Logging estruturado e métricas detalhadas
- Tripwires configuráveis
- Tratamento robusto de erros
"""

from .safety import (
    # Enums
    GuardrailType,
    SafetyLevel,
    
    # Modelos Pydantic
    SafetyValidationOutput,
    ContentFilterOutput,
    AviationSafetyOutput,
    RegulatoryComplianceOutput,
    PerformanceMonitorOutput,
    GuardrailFunctionOutput,
    GuardrailResult,
    GuardrailMetrics,
    
    # Classes principais
    ICAOValidator,
    ContentFilter,
    AviationSafety,
    RegulatoryCompliance,
    PerformanceMonitor,
    GuardrailManager,
)

__all__ = [
    # Enums
    "GuardrailType",
    "SafetyLevel",
    
    # Modelos Pydantic
    "SafetyValidationOutput",
    "ContentFilterOutput", 
    "AviationSafetyOutput",
    "RegulatoryComplianceOutput",
    "PerformanceMonitorOutput",
    "GuardrailFunctionOutput",
    "GuardrailResult",
    "GuardrailMetrics",
    
    # Classes principais
    "ICAOValidator",
    "ContentFilter",
    "AviationSafety",
    "RegulatoryCompliance", 
    "PerformanceMonitor",
    "GuardrailManager",
] 