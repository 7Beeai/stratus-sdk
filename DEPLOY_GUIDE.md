# 🚀 Guia de Deploy - Stratus.IA no Google Cloud

## 📊 **Recursos Necessários**

### **Estimativa de Custos (Cloud Run)**
- **Memória:** 512MB (recomendado)
- **CPU:** 1 vCPU
- **Instâncias:** 0-10 (auto-scaling)
- **Custo estimado:** ~$5-15/mês (dependendo do tráfego)

### **Tamanho da Aplicação**
- **Imagem Docker:** ~200MB
- **Código:** ~50MB
- **Dependências:** ~150MB

## 🛠️ **Pré-requisitos**

### 1. **Google Cloud CLI**
```bash
# Instalar gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Login
gcloud auth login
gcloud config set project 7bee-ai
```

### 2. **Variáveis de Ambiente**
```bash
export JWT_SECRET="sua-chave-secreta-super-segura"
export OPENAI_API_KEY="sua-chave-openai"
export PROJECT_ID="7bee-ai"
```

## 🚀 **Deploy Automatizado**

### **Opção 1: Script Automático**
```bash
chmod +x deploy.sh
./deploy.sh
```

### **Opção 2: Deploy Manual**

#### **1. Build da Imagem**
```bash
gcloud builds submit --config cloudbuild.yaml
```

#### **2. Deploy no Cloud Run**
```bash
gcloud run deploy stratus-ia \
  --image gcr.io/7bee-ai/stratus-ia:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --max-instances 10 \
  --min-instances 0 \
  --set-env-vars ENVIRONMENT=production \
  --set-secrets JWT_SECRET=jwt-secret:latest,OPENAI_API_KEY=openai-api-key:latest
```

## 🌐 **Configuração do Domínio**

### **1. Registrar Domínio (se necessário)**
```bash
# Verificar disponibilidade
gcloud domains list-user-verified

# Registrar domínio (se não tiver)
gcloud domains register api.stratus.7bee.ai
```

### **2. Configurar DNS**
```bash
# Mapear domínio para Cloud Run
gcloud run domain-mappings create \
  --service=stratus-ia \
  --domain=api.stratus.7bee.ai \
  --region=us-central1 \
  --force-override
```

### **3. Configurar SSL (automático)**
O Google Cloud Run fornece SSL automático para domínios mapeados.

## 🔧 **Configuração de Secrets**

### **1. Criar Secrets**
```bash
# JWT Secret
echo -n "sua-chave-secreta-super-segura" | \
gcloud secrets create jwt-secret --data-file=-

# OpenAI API Key
echo -n "sua-chave-openai" | \
gcloud secrets create openai-api-key --data-file=-
```

### **2. Atualizar Secrets**
```bash
# Atualizar JWT Secret
echo -n "nova-chave-secreta" | \
gcloud secrets versions add jwt-secret --data-file=-

# Atualizar OpenAI Key
echo -n "nova-chave-openai" | \
gcloud secrets versions add openai-api-key --data-file=-
```

## 📊 **Monitoramento**

### **1. Logs**
```bash
# Ver logs em tempo real
gcloud logs tail --project=7bee-ai --filter="resource.type=cloud_run_revision"

# Ver logs específicos
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=stratus-ia"
```

### **2. Métricas**
- Acesse: https://console.cloud.google.com/run
- Selecione o serviço `stratus-ia`
- Aba "Métricas" para ver performance

### **3. Health Check**
```bash
curl https://api.stratus.7bee.ai/health
```

## 🔄 **Atualizações**

### **Deploy de Nova Versão**
```bash
# 1. Commit das mudanças
git add .
git commit -m "Nova versão"
git push origin main

# 2. Deploy automático (se configurado Cloud Build trigger)
# OU deploy manual
./deploy.sh
```

### **Rollback**
```bash
# Listar revisões
gcloud run revisions list --service=stratus-ia --region=us-central1

# Fazer rollback
gcloud run services update-traffic stratus-ia \
  --to-revisions=REVISION_NAME=100 \
  --region=us-central1
```

## 🔒 **Segurança**

### **1. IAM e Permissões**
```bash
# Verificar permissões
gcloud projects get-iam-policy 7bee-ai

# Adicionar permissões específicas
gcloud projects add-iam-policy-binding 7bee-ai \
  --member="user:seu-email@gmail.com" \
  --role="roles/run.admin"
```

### **2. VPC Connector (se necessário)**
```bash
# Criar VPC Connector para recursos privados
gcloud compute networks vpc-access connectors create stratus-connector \
  --region=us-central1 \
  --range=10.8.0.0/28 \
  --network=default
```

## 💰 **Otimização de Custos**

### **1. Configurações Recomendadas**
- **Min Instances:** 0 (para economizar quando não há tráfego)
- **Max Instances:** 10 (limitar custos)
- **Memory:** 512Mi (suficiente para a aplicação)
- **CPU:** 1 (adequado para API)

### **2. Monitoramento de Custos**
```bash
# Ver custos do projeto
gcloud billing accounts list
gcloud billing projects describe 7bee-ai
```

## 🧪 **Testes Pós-Deploy**

### **1. Teste de Conectividade**
```bash
# Health Check
curl https://api.stratus.7bee.ai/health

# Info
curl https://api.stratus.7bee.ai/info

# Métricas
curl https://api.stratus.7bee.ai/metrics
```

### **2. Teste de Autenticação**
```bash
# Registro
curl -X POST https://api.stratus.7bee.ai/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Teste",
    "email": "teste@exemplo.com",
    "password": "Teste123!",
    "role": "pilot"
  }'

# Login
curl -X POST https://api.stratus.7bee.ai/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "teste@exemplo.com",
    "password": "Teste123!"
  }'
```

### **3. Teste de Chat**
```bash
# Chat (com token)
curl -X POST https://api.stratus.7bee.ai/chat \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Olá!",
    "message_type": "question"
  }'
```

## 🆘 **Troubleshooting**

### **Problemas Comuns**

#### **1. Erro de Build**
```bash
# Ver logs do build
gcloud builds log BUILD_ID
```

#### **2. Erro de Deploy**
```bash
# Ver logs do serviço
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=stratus-ia" --limit=50
```

#### **3. Domínio não funciona**
```bash
# Verificar mapeamento
gcloud run domain-mappings list --region=us-central1

# Verificar DNS
nslookup api.stratus.7bee.ai
```

## 📞 **Suporte**

Para problemas específicos:
1. Verifique os logs: `gcloud logs tail`
2. Teste localmente primeiro
3. Verifique configurações de secrets
4. Consulte a documentação do Google Cloud Run

---

**🎉 Sua API estará disponível em: https://api.stratus.7bee.ai** 