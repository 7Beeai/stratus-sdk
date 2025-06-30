# Multi-stage build para otimizar tamanho
FROM python:3.11-slim as builder

# Instala dependências de build
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Cria ambiente virtual
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copia requirements e instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Imagem final
FROM python:3.11-slim

# Metadados
LABEL maintainer="Stratus.IA Team"
LABEL version="1.0.0"
LABEL description="Stratus.IA - Assistente de Aviação com IA"

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/opt/venv/bin:$PATH"

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia ambiente virtual do builder
COPY --from=builder /opt/venv /opt/venv

# Cria usuário não-root
RUN groupadd -r stratus && useradd -r -g stratus stratus

# Cria diretórios
WORKDIR /app
RUN mkdir -p /app/logs /app/data && chown -R stratus:stratus /app

# Copia código da aplicação
COPY . .
RUN chown -R stratus:stratus /app

# Muda para usuário não-root
USER stratus

# Expõe porta
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando padrão
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"] 