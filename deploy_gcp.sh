#!/bin/bash

# 🚀 Script de Deploy Automatizado - Stratus.IA
# Google Cloud Console

set -e  # Parar em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
PROJECT_ID="7bee-ai"
REGION="us-central1"
SERVICE_NAME="stratus-ia"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
VERSION="v1"

echo -e "${BLUE}🚀 Iniciando deploy do Stratus.IA no Google Cloud...${NC}"

# Função para log
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERRO] $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}[AVISO] $1${NC}"
}

# 1. Verificar pré-requisitos
log "Verificando pré-requisitos..."

# Verificar se gcloud está instalado
if ! command -v gcloud &> /dev/null; then
    error "gcloud CLI não está instalado. Instale em: https://cloud.google.com/sdk/docs/install"
fi

# Verificar se docker está instalado
if ! command -v docker &> /dev/null; then
    error "Docker não está instalado. Instale em: https://docs.docker.com/get-docker/"
fi

# Verificar se está logado no gcloud
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    warning "Você não está logado no gcloud. Fazendo login..."
    gcloud auth login
fi

# 2. Configurar projeto
log "Configurando projeto: ${PROJECT_ID}"
gcloud config set project ${PROJECT_ID}

# 3. Verificar se projeto existe
if ! gcloud projects describe ${PROJECT_ID} &> /dev/null; then
    error "Projeto ${PROJECT_ID} não existe. Crie o projeto primeiro no Google Cloud Console."
fi

# 4. Habilitar APIs necessárias
log "Habilitando APIs necessárias..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    secretmanager.googleapis.com \
    containerregistry.googleapis.com \
    --quiet

# 5. Verificar/criar secrets
log "Verificando secrets..."

# JWT Secret
if ! gcloud secrets describe jwt-secret &> /dev/null; then
    warning "Secret 'jwt-secret' não encontrado. Criando..."
    if [ -z "$JWT_SECRET" ]; then
        JWT_SECRET=$(openssl rand -base64 32)
        warning "JWT_SECRET não definido. Gerando automaticamente: ${JWT_SECRET}"
    fi
    echo -n "$JWT_SECRET" | gcloud secrets create jwt-secret --data-file=-
fi

# OpenAI API Key
if ! gcloud secrets describe openai-api-key &> /dev/null; then
    warning "Secret 'openai-api-key' não encontrado. Criando..."
    if [ -z "$OPENAI_API_KEY" ]; then
        error "OPENAI_API_KEY não definido. Configure a variável de ambiente OPENAI_API_KEY"
    fi
    echo -n "$OPENAI_API_KEY" | gcloud secrets create openai-api-key --data-file=-
fi

# 6. Build da imagem Docker
log "Fazendo build da imagem Docker..."
docker build -t ${IMAGE_NAME}:${VERSION} .

if [ $? -ne 0 ]; then
    error "Erro no build da imagem Docker"
fi

# 7. Push da imagem
log "Fazendo push da imagem para Container Registry..."
docker push ${IMAGE_NAME}:${VERSION}

if [ $? -ne 0 ]; then
    error "Erro no push da imagem"
fi

# 8. Deploy no Cloud Run
log "Fazendo deploy no Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME}:${VERSION} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --max-instances 10 \
    --min-instances 0 \
    --port 8000 \
    --set-env-vars="ENVIRONMENT=production" \
    --set-secrets="JWT_SECRET=jwt-secret:latest" \
    --set-secrets="OPENAI_API_KEY=openai-api-key:latest" \
    --quiet

if [ $? -ne 0 ]; then
    error "Erro no deploy do Cloud Run"
fi

# 9. Obter URL do serviço
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format="value(status.url)")

log "Deploy concluído com sucesso! 🎉"
echo -e "${GREEN}📱 URL do serviço: ${SERVICE_URL}${NC}"
echo -e "${GREEN}🔍 Health Check: ${SERVICE_URL}/health${NC}"
echo -e "${GREEN}📚 Documentação: ${SERVICE_URL}/docs${NC}"

# 10. Testar health check
log "Testando health check..."
sleep 10  # Aguardar serviço inicializar

if curl -f "${SERVICE_URL}/health" &> /dev/null; then
    log "✅ Health check passou!"
else
    warning "⚠️ Health check falhou. Verifique os logs:"
    echo "gcloud logs tail --service=${SERVICE_NAME} --region=${REGION}"
fi

# 11. Comandos úteis
echo -e "${BLUE}📋 Comandos úteis:${NC}"
echo -e "${YELLOW}# Ver logs:${NC} gcloud logs tail --service=${SERVICE_NAME} --region=${REGION}"
echo -e "${YELLOW}# Ver status:${NC} gcloud run services describe ${SERVICE_NAME} --region=${REGION}"
echo -e "${YELLOW}# Escalar:${NC} gcloud run services update ${SERVICE_NAME} --region=${REGION} --memory=1Gi --cpu=2"
echo -e "${YELLOW}# Nova versão:${NC} ./deploy_gcp.sh"

log "Deploy finalizado! 🚀" 