# 🚀 Deploy Stratus.IA no Google Cloud Console

Guia completo para deploy da API Stratus.IA no Google Cloud Run usando o Cloud Console.

## 📋 Pré-requisitos

1. **Conta Google Cloud ativa**
2. **Projeto criado** (ex: `7bee-ai`)
3. **Billing habilitado**
4. **Cloud Shell ou terminal local com gcloud CLI**

## 🔧 Passo a Passo

### 1. **Preparar o Ambiente**

```bash
# Clone o repositório (se ainda não tiver)
git clone https://github.com/7Beeai/stratus-sdk.git
cd stratus-sdk

# Ou se já tem localmente, faça push das últimas alterações
git add .
git commit -m "Preparando para deploy"
git push origin main
```

### 2. **Configurar Variáveis de Ambiente**

```bash
# Criar arquivo .env
cp env.example .env

# Editar o arquivo .env com suas chaves reais
nano .env
```

**Configure estas variáveis no .env:**
```bash
ENVIRONMENT=production
OPENAI_API_KEY=sk-your-openai-key-here
JWT_SECRET=your-super-secret-jwt-key-here
GOOGLE_CLOUD_PROJECT=7bee-ai
GOOGLE_CLOUD_REGION=us-central1
```

### 3. **Habilitar APIs Necessárias**

```bash
# Configurar projeto
gcloud config set project 7bee-ai

# Habilitar APIs
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    secretmanager.googleapis.com \
    containerregistry.googleapis.com
```

### 4. **Criar Secrets no Secret Manager**

```bash
# Criar secret para JWT
echo -n "your-super-secret-jwt-key-here" | \
gcloud secrets create jwt-secret --data-file=-

# Criar secret para OpenAI
echo -n "sk-your-openai-key-here" | \
gcloud secrets create openai-api-key --data-file=-

# Criar secret para Pinecone (se usar)
echo -n "your-pinecone-key-here" | \
gcloud secrets create pinecone-api-key --data-file=-
```

### 5. **Build e Push da Imagem Docker**

```bash
# Build da imagem
docker build -t gcr.io/7bee-ai/stratus-ia:v1 .

# Push para Container Registry
docker push gcr.io/7bee-ai/stratus-ia:v1
```

### 6. **Deploy no Cloud Run**

```bash
# Deploy do serviço
gcloud run deploy stratus-ia \
    --image gcr.io/7bee-ai/stratus-ia:v1 \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --max-instances 10 \
    --min-instances 0 \
    --port 8000 \
    --set-env-vars="ENVIRONMENT=production" \
    --set-secrets="JWT_SECRET=jwt-secret:latest" \
    --set-secrets="OPENAI_API_KEY=openai-api-key:latest"
```

### 7. **Configurar Domínio Personalizado**

```bash
# Mapear domínio (opcional)
gcloud run domain-mappings create \
    --service stratus-ia \
    --domain api.stratus.7bee.ai \
    --region us-central1
```

### 8. **Verificar Deploy**

```bash
# Verificar status do serviço
gcloud run services describe stratus-ia --region us-central1

# Testar health check
curl https://stratus-ia-xxxxx-uc.a.run.app/health
```

## 🔍 Comandos de Verificação

### **Verificar Logs**
```bash
# Ver logs em tempo real
gcloud logs tail --service=stratus-ia --region=us-central1

# Ver logs específicos
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=stratus-ia" --limit=50
```

### **Verificar Métricas**
```bash
# Abrir console de métricas
gcloud monitoring dashboards list
```

### **Escalar Serviço**
```bash
# Ajustar recursos
gcloud run services update stratus-ia \
    --region us-central1 \
    --memory 1Gi \
    --cpu 2 \
    --max-instances 20
```

## 🚨 Troubleshooting

### **Erro: Permissão negada**
```bash
# Verificar permissões
gcloud auth list
gcloud config get-value account

# Se necessário, fazer login
gcloud auth login
```

### **Erro: API não habilitada**
```bash
# Habilitar API específica
gcloud services enable [API_NAME]
```

### **Erro: Imagem não encontrada**
```bash
# Verificar imagens disponíveis
gcloud container images list --repository=gcr.io/7bee-ai

# Rebuild se necessário
docker build -t gcr.io/7bee-ai/stratus-ia:v1 .
docker push gcr.io/7bee-ai/stratus-ia:v1
```

### **Erro: Secret não encontrado**
```bash
# Listar secrets
gcloud secrets list

# Recriar secret se necessário
echo -n "valor-do-secret" | gcloud secrets create nome-do-secret --data-file=-
```

## 📊 Monitoramento

### **Configurar Alertas**
```bash
# Criar política de alerta para erro 5xx
gcloud alpha monitoring policies create \
    --policy-from-file=alert-policy.yaml
```

### **Verificar Custos**
```bash
# Abrir console de billing
gcloud billing accounts list
```

## 🔄 Atualizações

### **Deploy de Nova Versão**
```bash
# Build nova versão
docker build -t gcr.io/7bee-ai/stratus-ia:v2 .

# Push nova versão
docker push gcr.io/7bee-ai/stratus-ia:v2

# Deploy nova versão
gcloud run deploy stratus-ia \
    --image gcr.io/7bee-ai/stratus-ia:v2 \
    --region us-central1
```

### **Rollback**
```bash
# Voltar para versão anterior
gcloud run services update-traffic stratus-ia \
    --to-revisions=REVISION_NAME=100 \
    --region us-central1
```

## 🌐 URLs Finais

Após o deploy, você terá:
- **URL do Cloud Run:** `https://stratus-ia-xxxxx-uc.a.run.app`
- **Health Check:** `https://stratus-ia-xxxxx-uc.a.run.app/health`
- **Documentação:** `https://stratus-ia-xxxxx-uc.a.run.app/docs`

## 📞 Suporte

Se encontrar problemas:
1. Verifique os logs: `gcloud logs tail --service=stratus-ia`
2. Verifique métricas no Console do Google Cloud
3. Consulte a documentação do Cloud Run
4. Abra um issue no repositório GitHub

---

**🎉 Deploy concluído! Sua API Stratus.IA está rodando no Google Cloud!** 