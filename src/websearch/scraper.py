"""
Content Scraper para Stratus.IA
Responsável por extrair e processar conteúdo de páginas web relacionadas à aviação
"""

import asyncio
import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlparse, urljoin
import aiohttp
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from .base import (
    ContentType, 
    SourceReliability, 
    ScrapingMetrics,
    ScrapingStatus
)
from ..utils.logging import get_logger


class ScrapedContent(BaseModel):
    """Conteúdo extraído de uma página web"""
    url: str = Field(..., description="URL da página")
    title: str = Field(..., description="Título da página")
    content: str = Field(..., description="Conteúdo principal extraído")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadados extraídos")
    structured_data: Dict[str, Any] = Field(default_factory=dict, description="Dados estruturados")
    content_type: ContentType = Field(..., description="Tipo de conteúdo")
    source_reliability: SourceReliability = Field(..., description="Confiabilidade da fonte")
    extraction_timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp da extração")
    status: ScrapingStatus = Field(default=ScrapingStatus.SUCCESS, description="Status da extração")


class ScrapingConfig(BaseModel):
    """Configuração para scraping"""
    timeout: int = Field(default=30, description="Timeout em segundos")
    max_retries: int = Field(default=3, description="Máximo de tentativas")
    rate_limit_delay: float = Field(default=1.0, description="Delay entre requisições em segundos")
    max_content_length: int = Field(default=100000, description="Tamanho máximo do conteúdo")
    user_agent: str = Field(
        default="Stratus.IA/1.0 (Aviation Content Scraper)",
        description="User-Agent para requisições"
    )
    cache_ttl: timedelta = Field(
        default=timedelta(hours=1),
        description="TTL do cache de conteúdo"
    )


class StratusContentScraper:
    """Scraper especializado para conteúdo de aviação"""
    
    def __init__(self, config: Optional[ScrapingConfig] = None):
        self.config = config or ScrapingConfig()
        self.logger = get_logger()
        self.metrics = ScrapingMetrics()
        
        # Cache de conteúdo
        self.content_cache: Dict[str, Dict[str, Any]] = {}
        
        # Rate limiting
        self.last_request_time = datetime.now()
        
        # Headers para requisições
        self.headers = {
            'User-Agent': self.config.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Padrões de extração específicos para aviação
        self.extraction_patterns = {
            ContentType.METAR_TAF: {
                'metar': r'METAR\s+[A-Z]{4}\s+\d{6}Z\s+[A-Z0-9\s/]+',
                'taf': r'TAF\s+[A-Z]{4}\s+\d{6}Z\s+[A-Z0-9\s/]+',
                'icao': r'\b[A-Z]{4}\b',
                'time': r'\d{6}Z',
                'wind': r'\d{3}\d{2,3}KT',
                'visibility': r'\d{4}',
                'weather': r'[A-Z]{2,3}',
            },
            ContentType.NOTAM: {
                'notam_id': r'[A-Z]\d{4}/\d{2}',
                'icao': r'\b[A-Z]{4}\b',
                'coordinates': r'\d{1,2}°\d{1,2}\'[NS]\s+\d{1,3}°\d{1,2}\'[EW]',
                'radius': r'RADIUS\s+\d+\s+[A-Z]+',
                'altitude': r'[A-Z]+\s+\d+\s+[A-Z]+',
                'time_period': r'\d{6}\s+\d{6}',
            },
            ContentType.REGULATION: {
                'rbac': r'RBAC\s+\d+[A-Z]?',
                'ica': r'ICA\s+\d+[A-Z]?',
                'portaria': r'Portaria\s+\d+/\d+',
                'instrução': r'Instrução\s+\d+/\d+',
                'norma': r'Norma\s+\d+/\d+',
            },
            ContentType.EMERGENCY: {
                'mayday': r'MAYDAY|MAYDAY|MAYDAY',
                'pan_pan': r'PAN\s+PAN|PAN\s+PAN',
                'emergency': r'EMERGENCY|EMERGÊNCIA',
                'socorro': r'SOCORRO|SOS',
                'falha': r'FALHA|FAILURE|MALFUNCTION',
            }
        }
        
        # Seletores CSS para diferentes tipos de conteúdo
        self.css_selectors = {
            'title': ['h1', 'h2', '.title', '.headline', 'title'],
            'content': ['.content', '.main', '.article', '.post', 'main', 'article'],
            'metadata': ['.meta', '.info', '.details', '.summary'],
            'navigation': ['.nav', '.menu', '.breadcrumb', '.sidebar'],
        }
    
    async def scrape_content(
        self, 
        url: str, 
        content_type: Optional[ContentType] = None,
        force_fresh: bool = False
    ) -> Optional[ScrapedContent]:
        """Extrai conteúdo de uma página web"""
        start_time = datetime.now()
        
        try:
            # Verifica cache
            if not force_fresh:
                cached_content = self._get_cached_content(url)
                if cached_content:
                    self.logger._log_info(f"Cache hit para URL: {url}")
                    self.metrics.cache_hit_rate = self._update_cache_hit_rate(True)
                    return cached_content
            
            # Rate limiting
            await self._rate_limit()
            
            # Faz requisição HTTP
            html_content = await self._fetch_url(url)
            if not html_content:
                return None
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extrai conteúdo básico
            title = self._extract_title(soup)
            content = self._extract_main_content(soup)
            metadata = self._extract_metadata(soup)
            
            # Detecta tipo de conteúdo se não fornecido
            if content_type is None:
                content_type = self._detect_content_type(title, content)
            
            # Determina confiabilidade da fonte
            source_reliability = self._assess_source_reliability(url)
            
            # Extrai dados estruturados
            structured_data = self._extract_structured_data(content, content_type)
            
            # Cria objeto de conteúdo
            scraped_content = ScrapedContent(
                url=url,
                title=title,
                content=content,
                metadata=metadata,
                structured_data=structured_data,
                content_type=content_type,
                source_reliability=source_reliability,
                status=ScrapingStatus.SUCCESS
            )
            
            # Atualiza cache
            self._cache_content(url, scraped_content)
            
            # Atualiza métricas
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(True, execution_time, len(content))
            
            self.logger._log_info(
                f"Conteúdo extraído: {len(content)} caracteres em {execution_time:.2f}s",
                extra={
                    "url": url,
                    "content_type": content_type.value,
                    "content_length": len(content)
                }
            )
            
            return scraped_content
            
        except Exception as e:
            self.logger._log_error(f"Erro ao extrair conteúdo de {url}: {str(e)}")
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(False, execution_time, 0)
            
            return ScrapedContent(
                url=url,
                title="",
                content="",
                content_type=ContentType.GENERAL,
                source_reliability=SourceReliability.UNRELIABLE,
                status=ScrapingStatus.FAILED
            )
    
    async def _fetch_url(self, url: str) -> Optional[str]:
        """Faz requisição HTTP para a URL"""
        for attempt in range(self.config.max_retries):
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                    headers=self.headers
                ) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            content = await response.text()
                            
                            # Verifica tamanho do conteúdo
                            if len(content) > self.config.max_content_length:
                                self.logger._log_warning(f"Conteúdo muito grande: {len(content)} caracteres")
                                content = content[:self.config.max_content_length]
                            
                            return content
                        else:
                            self.logger._log_warning(f"HTTP {response.status} para {url}")
                            
            except asyncio.TimeoutError:
                self.logger._log_warning(f"Timeout na tentativa {attempt + 1} para {url}")
            except Exception as e:
                self.logger._log_warning(f"Erro na tentativa {attempt + 1} para {url}: {str(e)}")
            
            # Aguarda antes da próxima tentativa
            if attempt < self.config.max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Backoff exponencial
        
        return None
    
    async def _rate_limit(self):
        """Implementa rate limiting"""
        now = datetime.now()
        time_since_last = (now - self.last_request_time).total_seconds()
        
        if time_since_last < self.config.rate_limit_delay:
            delay = self.config.rate_limit_delay - time_since_last
            await asyncio.sleep(delay)
        
        self.last_request_time = datetime.now()
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extrai título da página"""
        # Tenta diferentes seletores
        for selector in self.css_selectors['title']:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                if title:
                    return title
        
        # Fallback para tag title
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)
        
        return "Sem título"
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extrai conteúdo principal da página"""
        # Remove elementos desnecessários
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        
        # Tenta seletores específicos para conteúdo
        for selector in self.css_selectors['content']:
            element = soup.select_one(selector)
            if element:
                content = element.get_text(separator=' ', strip=True)
                if len(content) > 100:  # Conteúdo mínimo
                    return content
        
        # Fallback para body
        body = soup.find('body')
        if body:
            return body.get_text(separator=' ', strip=True)
        
        return ""
    
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extrai metadados da página"""
        metadata = {}
        
        # Meta tags
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            name = tag.get('name') or tag.get('property')
            content = tag.get('content')
            if name and content:
                metadata[name] = content
        
        # Structured data (JSON-LD)
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                import json
                data = json.loads(script.string)
                metadata['structured_data'] = data
            except:
                continue
        
        # Open Graph tags
        og_tags = soup.find_all('meta', property=lambda x: x and x.startswith('og:'))
        for tag in og_tags:
            property_name = tag.get('property', '').replace('og:', '')
            content = tag.get('content')
            if property_name and content:
                metadata[f'og_{property_name}'] = content
        
        return metadata
    
    def _detect_content_type(self, title: str, content: str) -> ContentType:
        """Detecta automaticamente o tipo de conteúdo"""
        text = (title + " " + content).lower()
        
        # Verifica padrões específicos
        for content_type, patterns in self.extraction_patterns.items():
            for pattern_name, pattern in patterns.items():
                if re.search(pattern, text, re.IGNORECASE):
                    return content_type
        
        # Verifica palavras-chave gerais
        if any(kw in text for kw in ["metar", "taf", "meteorologia"]):
            return ContentType.METAR_TAF
        elif any(kw in text for kw in ["notam", "aviso", "restrição"]):
            return ContentType.NOTAM
        elif any(kw in text for kw in ["rbac", "regulamento", "norma"]):
            return ContentType.REGULATION
        elif any(kw in text for kw in ["emergência", "socorro", "falha"]):
            return ContentType.EMERGENCY
        elif any(kw in text for kw in ["técnico", "manual", "procedimento"]):
            return ContentType.TECHNICAL
        elif any(kw in text for kw in ["notícia", "novo", "atualização"]):
            return ContentType.NEWS
        else:
            return ContentType.GENERAL
    
    def _assess_source_reliability(self, url: str) -> SourceReliability:
        """Avalia confiabilidade da fonte baseada na URL"""
        domain = urlparse(url).netloc.lower()
        domain = domain.replace('www.', '')
        
        # Fontes oficiais conhecidas
        official_domains = {
            'anac.gov.br': SourceReliability.OFFICIAL,
            'decea.gov.br': SourceReliability.OFFICIAL,
            'icao.int': SourceReliability.OFFICIAL,
            'faa.gov': SourceReliability.OFFICIAL,
            'easa.europa.eu': SourceReliability.OFFICIAL,
        }
        
        for official_domain, reliability in official_domains.items():
            if official_domain in domain:
                return reliability
        
        # Avaliação baseada em padrões
        if any(official in domain for official in ['.gov.', '.mil.', '.org']):
            return SourceReliability.VERIFIED
        elif any(commercial in domain for commercial in ['.com.br', '.com']):
            return SourceReliability.RELIABLE
        else:
            return SourceReliability.QUESTIONABLE
    
    def _extract_structured_data(self, content: str, content_type: ContentType) -> Dict[str, Any]:
        """Extrai dados estruturados baseado no tipo de conteúdo"""
        structured_data = {}
        
        if content_type in self.extraction_patterns:
            patterns = self.extraction_patterns[content_type]
            
            for data_type, pattern in patterns.items():
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    structured_data[data_type] = matches
        
        # Extrai dados gerais
        general_patterns = {
            'icao_codes': r'\b[A-Z]{4}\b',
            'coordinates': r'\d{1,2}°\d{1,2}\'[NS]\s+\d{1,3}°\d{1,2}\'[EW]',
            'times': r'\d{6}Z?',
            'dates': r'\d{2}/\d{2}/\d{4}',
            'phone_numbers': r'\(\d{2}\)\s*\d{4,5}-\d{4}',
            'emails': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        }
        
        for data_type, pattern in general_patterns.items():
            matches = re.findall(pattern, content)
            if matches:
                structured_data[data_type] = matches
        
        return structured_data
    
    def _get_cached_content(self, url: str) -> Optional[ScrapedContent]:
        """Recupera conteúdo do cache"""
        cache_key = hashlib.md5(url.encode()).hexdigest()
        
        if cache_key in self.content_cache:
            cached_data = self.content_cache[cache_key]
            
            # Verifica se não expirou
            if datetime.now() - cached_data['timestamp'] < self.config.cache_ttl:
                return cached_data['content']
            else:
                # Remove entrada expirada
                del self.content_cache[cache_key]
        
        return None
    
    def _cache_content(self, url: str, content: ScrapedContent):
        """Armazena conteúdo no cache"""
        cache_key = hashlib.md5(url.encode()).hexdigest()
        
        self.content_cache[cache_key] = {
            'content': content,
            'timestamp': datetime.now()
        }
        
        # Limita tamanho do cache
        if len(self.content_cache) > 500:
            # Remove entradas mais antigas
            oldest_key = min(
                self.content_cache.keys(),
                key=lambda k: self.content_cache[k]['timestamp']
            )
            del self.content_cache[oldest_key]
    
    def _update_metrics(self, success: bool, execution_time: float, content_length: int):
        """Atualiza métricas do scraper"""
        self.metrics.total_scrapes += 1
        
        if success:
            self.metrics.successful_scrapes += 1
        else:
            self.metrics.failed_scrapes += 1
        
        # Atualiza média de tempo de execução
        if self.metrics.avg_execution_time == 0:
            self.metrics.avg_execution_time = execution_time
        else:
            total_time = self.metrics.avg_execution_time * (self.metrics.total_scrapes - 1) + execution_time
            self.metrics.avg_execution_time = total_time / self.metrics.total_scrapes
        
        # Atualiza média de tamanho do conteúdo
        if self.metrics.avg_content_length == 0:
            self.metrics.avg_content_length = content_length
        else:
            total_length = self.metrics.avg_content_length * (self.metrics.successful_scrapes - 1) + content_length
            self.metrics.avg_content_length = total_length / self.metrics.successful_scrapes if self.metrics.successful_scrapes > 0 else 0
        
        self.metrics.last_scrape = datetime.now()
    
    def _update_cache_hit_rate(self, cache_hit: bool) -> float:
        """Atualiza taxa de cache hit"""
        if cache_hit:
            return min(self.metrics.cache_hit_rate + 0.01, 1.0)
        else:
            return max(self.metrics.cache_hit_rate - 0.01, 0.0)
    
    async def scrape_multiple_urls(
        self, 
        urls: List[str], 
        max_concurrent: int = 5
    ) -> List[ScrapedContent]:
        """Extrai conteúdo de múltiplas URLs em paralelo"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_semaphore(url: str) -> Optional[ScrapedContent]:
            async with semaphore:
                return await self.scrape_content(url)
        
        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filtra resultados válidos
        valid_results = []
        for result in results:
            if isinstance(result, ScrapedContent):
                valid_results.append(result)
            elif isinstance(result, Exception):
                self.logger._log_error(f"Erro ao extrair conteúdo: {str(result)}")
        
        return valid_results
    
    def get_metrics(self) -> ScrapingMetrics:
        """Retorna métricas atuais do scraper"""
        return self.metrics
    
    def clear_cache(self):
        """Limpa o cache de conteúdo"""
        self.content_cache.clear()
        self.logger._log_info("Cache de conteúdo limpo") 