#!/bin/bash
# Script de Deploy para Google Cloud Run com Domínio Personalizado

set -e

echo "🚀 Iniciando Deploy do Stratus.IA no Google Cloud..."

# Configurações
PROJECT_ID="7bee-ai"  # Substitua pelo seu Project ID
REGION="us-central1"
SERVICE_NAME="stratus-ia"
DOMAIN="api.stratus.7bee.ai"

# Verifica se está logado no gcloud
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ Não está logado no Google Cloud. Execute: gcloud auth login"
    exit 1
fi

# Define projeto
gcloud config set project $PROJECT_ID

# Habilita APIs necessárias
echo "📋 Habilitando APIs necessárias..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    secretmanager.googleapis.com \
    domains.googleapis.com \
    dns.googleapis.com

# Cria secrets (se não existirem)
echo "🔐 Configurando secrets..."
echo -n "$JWT_SECRET" | gcloud secrets create jwt-secret --data-file=- 2>/dev/null || echo "Secret jwt-secret já existe"
echo -n "$OPENAI_API_KEY" | gcloud secrets create openai-api-key --data-file=- 2>/dev/null || echo "Secret openai-api-key já existe"

# Build e deploy
echo "🏗️ Fazendo build e deploy..."
gcloud builds submit --config cloudbuild.yaml

# Configura domínio personalizado
echo "🌐 Configurando domínio personalizado..."
gcloud run domain-mappings create \
    --service=$SERVICE_NAME \
    --domain=$DOMAIN \
    --region=$REGION \
    --force-override

# Obtém URL do serviço
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo "✅ Deploy concluído!"
echo "🌐 URL do serviço: $SERVICE_URL"
echo "🔗 Domínio personalizado: https://$DOMAIN"
echo "🏥 Health check: https://$DOMAIN/health"

# Testa health check
echo "🏥 Testando health check..."
sleep 10  # Aguarda o serviço estar pronto
curl -f "https://$DOMAIN/health" || echo "⚠️ Health check falhou - aguarde alguns minutos"

echo "🎉 Stratus.IA está rodando em produção!"
echo ""
echo "📋 Próximos passos:"
echo "1. Configure DNS do domínio $DOMAIN para apontar para o Cloud Run"
echo "2. Teste a API: curl https://$DOMAIN/health"
echo "3. Configure integração N8N com a URL: https://$DOMAIN" 