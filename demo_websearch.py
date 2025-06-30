#!/usr/bin/env python3
"""
Demonstração do Sistema de Websearch para Stratus.IA
Testa todos os componentes: Search Engine, Scraper, Validator e Knowledge Updater
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import List

# Adiciona o diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.websearch.engine import StratusWebSearchEngine
from src.websearch.scraper import StratusContentScraper, ScrapingConfig
from src.websearch.validator import StratusSearchValidator, ValidationConfig
from src.websearch.updater import StratusKnowledgeUpdater, UpdateConfig
from src.websearch.base import SearchDomain, ContentType, SourceReliability
from src.utils.logging import get_logger


class WebSearchDemo:
    """Demonstração completa do sistema de websearch"""
    
    def __init__(self):
        self.logger = get_logger()
        
        # Inicializa componentes
        self.search_engine = StratusWebSearchEngine()
        self.scraper = StratusContentScraper()
        self.validator = StratusSearchValidator()
        self.knowledge_updater = StratusKnowledgeUpdater()
        
        # Queries de teste
        self.test_queries = [
            "METAR SBGR",
            "NOTAM SBSP",
            "RBAC 91",
            "emergência aeronáutica",
            "DECEA meteorologia",
            "ANAC regulamentos",
            "ICAO procedimentos",
            "aeroporto Congonhas",
            "pista 09L SBGR",
            "visibilidade tempo"
        ]
        
        # URLs de teste para scraping
        self.test_urls = [
            "https://www.anac.gov.br",
            "https://www.decea.gov.br",
            "https://www.icao.int",
            "https://www.faa.gov",
            "https://www.easa.europa.eu"
        ]
    
    async def run_demo(self):
        """Executa demonstração completa"""
        self.logger._log_info("🚀 Iniciando demonstração do Sistema de Websearch")
        self.logger._log_info("=" * 60)
        
        try:
            # 1. Teste do Web Search Engine
            await self.demo_search_engine()
            
            # 2. Teste do Content Scraper
            await self.demo_content_scraper()
            
            # 3. Teste do Search Result Validator
            await self.demo_search_validator()
            
            # 4. Teste do Knowledge Updater
            await self.demo_knowledge_updater()
            
            # 5. Teste integrado
            await self.demo_integrated_workflow()
            
            # 6. Exibe métricas finais
            self.show_final_metrics()
            
        except Exception as e:
            self.logger._log_error(f"Erro na demonstração: {str(e)}")
            raise
    
    async def demo_search_engine(self):
        """Demonstra o Web Search Engine"""
        self.logger._log_info("🔍 Testando Web Search Engine")
        self.logger._log_info("-" * 40)
        
        for i, query in enumerate(self.test_queries[:3], 1):
            self.logger._log_info(f"Query {i}: {query}")
            
            try:
                # Executa busca
                results = await self.search_engine.search(
                    query=query,
                    max_results=5,
                    force_fresh=True
                )
                
                self.logger._log_info(f"  ✅ Resultados encontrados: {len(results)}")
                
                # Exibe primeiros resultados
                for j, result in enumerate(results[:2], 1):
                    self.logger._log_info(f"    {j}. {result.title[:50]}...")
                    self.logger._log_info(f"       URL: {result.url}")
                    self.logger._log_info(f"       Tipo: {result.content_type.value}")
                    self.logger._log_info(f"       Confiabilidade: {result.source_reliability.value}")
                    self.logger._log_info(f"       Score: {result.relevance_score:.2f}")
                
                await asyncio.sleep(1)  # Rate limiting
                
            except Exception as e:
                self.logger._log_error(f"  ❌ Erro na busca: {str(e)}")
        
        # Exibe métricas do search engine
        metrics = self.search_engine.get_metrics()
        self.logger._log_info(f"📊 Métricas do Search Engine:")
        self.logger._log_info(f"   Total de buscas: {metrics.total_searches}")
        self.logger._log_info(f"   Taxa de sucesso: {metrics.successful_searches}/{metrics.total_searches}")
        self.logger._log_info(f"   Tempo médio: {metrics.avg_response_time:.2f}s")
        self.logger._log_info(f"   Taxa de cache: {metrics.cache_hit_rate:.2f}")
    
    async def demo_content_scraper(self):
        """Demonstra o Content Scraper"""
        self.logger._log_info("\n📄 Testando Content Scraper")
        self.logger._log_info("-" * 40)
        
        for i, url in enumerate(self.test_urls[:3], 1):
            self.logger._log_info(f"URL {i}: {url}")
            
            try:
                # Executa scraping
                scraped_content = await self.scraper.scrape_content(
                    url=url,
                    force_fresh=True
                )
                
                if scraped_content and scraped_content.status.value == "SUCCESS":
                    self.logger._log_info(f"  ✅ Conteúdo extraído: {len(scraped_content.content)} caracteres")
                    self.logger._log_info(f"     Título: {scraped_content.title[:50]}...")
                    self.logger._log_info(f"     Tipo: {scraped_content.content_type.value}")
                    self.logger._log_info(f"     Confiabilidade: {scraped_content.source_reliability.value}")
                    
                    # Exibe dados estruturados se disponíveis
                    if scraped_content.structured_data:
                        self.logger._log_info(f"     Dados estruturados: {len(scraped_content.structured_data)} campos")
                else:
                    self.logger._log_warning(f"  ⚠️ Falha no scraping: {scraped_content.status.value if scraped_content else 'N/A'}")
                
                await asyncio.sleep(2)  # Rate limiting
                
            except Exception as e:
                self.logger._log_error(f"  ❌ Erro no scraping: {str(e)}")
        
        # Exibe métricas do scraper
        metrics = self.scraper.get_metrics()
        self.logger._log_info(f"📊 Métricas do Scraper:")
        self.logger._log_info(f"   Total de scrapes: {metrics.total_scrapes}")
        self.logger._log_info(f"   Taxa de sucesso: {metrics.successful_scrapes}/{metrics.total_scrapes}")
        self.logger._log_info(f"   Tempo médio: {metrics.avg_execution_time:.2f}s")
        self.logger._log_info(f"   Taxa de cache: {metrics.cache_hit_rate:.2f}")
    
    async def demo_search_validator(self):
        """Demonstra o Search Result Validator"""
        self.logger._log_info("\n✅ Testando Search Result Validator")
        self.logger._log_info("-" * 40)
        
        # Cria resultados simulados para teste
        from src.websearch.base import SearchResult
        
        test_results = [
            SearchResult(
                url="https://www.anac.gov.br/notam",
                title="NOTAM - Avisos aos Aeronavegantes",
                snippet="Informações sobre NOTAMs e avisos importantes para pilotos",
                content="Conteúdo detalhado sobre NOTAMs...",
                source_reliability=SourceReliability.OFFICIAL,
                content_type=ContentType.NOTAM,
                relevance_score=0.9,
                freshness_score=0.8,
                authority_score=1.0,
                extracted_data={"icao_codes": ["SBGR", "SBSP"], "notam_id": ["A1234/23"]}
            ),
            SearchResult(
                url="https://www.decea.gov.br/metar",
                title="METAR SBGR - Aeroporto de Congonhas",
                snippet="Condições meteorológicas atuais do aeroporto",
                content="METAR SBGR 261200Z 08008KT 9999 FEW020 SCT100 25/18 Q1018",
                source_reliability=SourceReliability.OFFICIAL,
                content_type=ContentType.METAR_TAF,
                relevance_score=0.8,
                freshness_score=0.9,
                authority_score=1.0,
                extracted_data={"icao_codes": ["SBGR"], "metar_data": ["METAR SBGR 261200Z 08008KT 9999 FEW020 SCT100 25/18 Q1018"]}
            ),
            SearchResult(
                url="https://spam-site.com/fake",
                title="Fake Aviation News",
                snippet="Conteúdo suspeito e não confiável",
                content="Spam content...",
                source_reliability=SourceReliability.UNRELIABLE,
                content_type=ContentType.GENERAL,
                relevance_score=0.2,
                freshness_score=0.1,
                authority_score=0.1,
                extracted_data={}
            )
        ]
        
        for i, result in enumerate(test_results, 1):
            self.logger._log_info(f"Resultado {i}: {result.title[:30]}...")
            
            try:
                # Valida resultado
                validation = await self.validator.validate_result(result)
                
                self.logger._log_info(f"  ✅ Válido: {validation.is_valid}")
                self.logger._log_info(f"     Score: {validation.validation_score:.2f}")
                self.logger._log_info(f"     Status: {validation.validation_status.value}")
                self.logger._log_info(f"     Confiança: {validation.confidence_score:.2f}")
                
                if validation.validation_errors:
                    self.logger._log_info(f"     Erros: {validation.validation_errors}")
                if validation.validation_warnings:
                    self.logger._log_info(f"     Avisos: {validation.validation_warnings}")
                
            except Exception as e:
                self.logger._log_error(f"  ❌ Erro na validação: {str(e)}")
        
        # Exibe métricas do validator
        metrics = self.validator.get_metrics()
        self.logger._log_info(f"📊 Métricas do Validator:")
        self.logger._log_info(f"   Total de validações: {metrics.total_validations}")
        self.logger._log_info(f"   Resultados válidos: {metrics.valid_results}")
        self.logger._log_info(f"   Resultados inválidos: {metrics.invalid_results}")
        self.logger._log_info(f"   Tempo médio: {metrics.avg_execution_time:.2f}s")
    
    async def demo_knowledge_updater(self):
        """Demonstra o Knowledge Updater"""
        self.logger._log_info("\n🔄 Testando Knowledge Updater")
        self.logger._log_info("-" * 40)
        
        # Cria resultados simulados para atualização
        from src.websearch.base import SearchResult
        
        test_results = [
            SearchResult(
                url="https://www.anac.gov.br/rbac91",
                title="RBAC 91 - Regulamento Brasileiro de Aviação Civil",
                snippet="Regulamento que estabelece as regras gerais de voo",
                content="Conteúdo detalhado do RBAC 91...",
                source_reliability=SourceReliability.OFFICIAL,
                content_type=ContentType.REGULATION,
                relevance_score=0.9,
                freshness_score=0.7,
                authority_score=1.0,
                extracted_data={"rbac_references": ["RBAC 91"], "regulation_numbers": ["91/001"]}
            ),
            SearchResult(
                url="https://www.decea.gov.br/emergency",
                title="Procedimentos de Emergência Aeronáutica",
                snippet="Protocolos para situações de emergência em voo",
                content="Procedimentos detalhados para emergências...",
                source_reliability=SourceReliability.OFFICIAL,
                content_type=ContentType.EMERGENCY,
                relevance_score=0.95,
                freshness_score=0.9,
                authority_score=1.0,
                extracted_data={"emergency_keywords": ["EMERGENCY", "MAYDAY"], "priority_levels": ["CRÍTICO"]}
            )
        ]
        
        try:
            # Processa resultados para atualização
            updates = await self.knowledge_updater.process_search_results(
                results=test_results,
                force_update=True
            )
            
            self.logger._log_info(f"  ✅ Atualizações criadas: {len(updates)}")
            
            for i, update in enumerate(updates, 1):
                self.logger._log_info(f"    {i}. {update.content_type.value} - Prioridade: {update.priority}")
                self.logger._log_info(f"       ID: {update.id[:8]}...")
                self.logger._log_info(f"       Status: {update.status.value}")
            
            # Executa atualizações
            if updates:
                executed_updates = await self.knowledge_updater.execute_updates(updates)
                self.logger._log_info(f"  ✅ Atualizações executadas: {len(executed_updates)}")
                
                for update in executed_updates:
                    self.logger._log_info(f"    - {update.id[:8]}... -> {update.status.value}")
            
        except Exception as e:
            self.logger._log_error(f"  ❌ Erro no knowledge updater: {str(e)}")
        
        # Exibe métricas do knowledge updater
        metrics = self.knowledge_updater.get_metrics()
        self.logger._log_info(f"📊 Métricas do Knowledge Updater:")
        self.logger._log_info(f"   Total de atualizações: {metrics.total_updates}")
        self.logger._log_info(f"   Atualizações bem-sucedidas: {metrics.successful_updates}")
        self.logger._log_info(f"   Taxa de sucesso: {metrics.success_rate:.2f}")
    
    async def demo_integrated_workflow(self):
        """Demonstra workflow integrado"""
        self.logger._log_info("\n🔄 Testando Workflow Integrado")
        self.logger._log_info("-" * 40)
        
        query = "METAR SBGR tempo atual"
        self.logger._log_info(f"Query: {query}")
        
        try:
            # 1. Busca
            self.logger._log_info("1️⃣ Executando busca...")
            search_results = await self.search_engine.search(query, max_results=3)
            self.logger._log_info(f"   Resultados encontrados: {len(search_results)}")
            
            if not search_results:
                self.logger._log_warning("   Nenhum resultado encontrado")
                return
            
            # 2. Validação
            self.logger._log_info("2️⃣ Validando resultados...")
            validation_results = await self.validator.validate_multiple_results(search_results)
            valid_results = [vr.search_result for vr in validation_results if vr.is_valid]
            self.logger._log_info(f"   Resultados válidos: {len(valid_results)}")
            
            # 3. Scraping (para o primeiro resultado válido)
            if valid_results:
                self.logger._log_info("3️⃣ Extraindo conteúdo...")
                scraped_content = await self.scraper.scrape_content(valid_results[0].url)
                if scraped_content:
                    self.logger._log_info(f"   Conteúdo extraído: {len(scraped_content.content)} caracteres")
                    self.logger._log_info(f"   Tipo: {scraped_content.content_type.value}")
            
            # 4. Atualização de conhecimento
            self.logger._log_info("4️⃣ Atualizando conhecimento...")
            updates = await self.knowledge_updater.process_search_results(valid_results)
            self.logger._log_info(f"   Atualizações criadas: {len(updates)}")
            
            if updates:
                executed = await self.knowledge_updater.execute_updates(updates)
                self.logger._log_info(f"   Atualizações executadas: {len(executed)}")
            
            self.logger._log_info("✅ Workflow integrado concluído com sucesso!")
            
        except Exception as e:
            self.logger._log_error(f"❌ Erro no workflow integrado: {str(e)}")
    
    def show_final_metrics(self):
        """Exibe métricas finais de todos os componentes"""
        self.logger._log_info("\n📊 Métricas Finais do Sistema")
        self.logger._log_info("=" * 60)
        
        # Search Engine
        se_metrics = self.search_engine.get_metrics()
        self.logger._log_info("🔍 Web Search Engine:")
        self.logger._log_info(f"   Buscas: {se_metrics.total_searches}")
        self.logger._log_info(f"   Sucesso: {se_metrics.successful_searches}")
        self.logger._log_info(f"   Tempo médio: {se_metrics.avg_response_time:.2f}s")
        self.logger._log_info(f"   Cache hit: {se_metrics.cache_hit_rate:.2f}")
        
        # Scraper
        sc_metrics = self.scraper.get_metrics()
        self.logger._log_info("\n📄 Content Scraper:")
        self.logger._log_info(f"   Scrapes: {sc_metrics.total_scrapes}")
        self.logger._log_info(f"   Sucesso: {sc_metrics.successful_scrapes}")
        self.logger._log_info(f"   Tempo médio: {sc_metrics.avg_execution_time:.2f}s")
        self.logger._log_info(f"   Cache hit: {sc_metrics.cache_hit_rate:.2f}")
        
        # Validator
        val_metrics = self.validator.get_metrics()
        self.logger._log_info("\n✅ Search Validator:")
        self.logger._log_info(f"   Validações: {val_metrics.total_validations}")
        self.logger._log_info(f"   Válidos: {val_metrics.valid_results}")
        self.logger._log_info(f"   Inválidos: {val_metrics.invalid_results}")
        self.logger._log_info(f"   Tempo médio: {val_metrics.avg_execution_time:.2f}s")
        
        # Knowledge Updater
        ku_metrics = self.knowledge_updater.get_metrics()
        self.logger._log_info("\n🔄 Knowledge Updater:")
        self.logger._log_info(f"   Atualizações: {ku_metrics.total_updates}")
        self.logger._log_info(f"   Sucesso: {ku_metrics.successful_updates}")
        self.logger._log_info(f"   Taxa de sucesso: {ku_metrics.success_rate:.2f}")
        
        self.logger._log_info("\n🎉 Demonstração concluída com sucesso!")


async def main():
    """Função principal"""
    # Verifica se a API key está definida
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ Erro: OPENAI_API_KEY não está definida")
        print("Por favor, defina a variável de ambiente:")
        print("export OPENAI_API_KEY='sua-api-key-aqui'")
        return
    
    # Cria e executa demonstração
    demo = WebSearchDemo()
    await demo.run_demo()


if __name__ == "__main__":
    asyncio.run(main()) 