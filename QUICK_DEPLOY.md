# ⚡ Deploy Rápido - Stratus.IA

## 🚀 Deploy em 3 Passos

### 1. **Configurar Variáveis**
```bash
# Exportar suas chaves
export OPENAI_API_KEY="sk-your-openai-key-here"
export JWT_SECRET="your-super-secret-jwt-key-here"

# Ou criar arquivo .env
cp env.example .env
# Editar .env com suas chaves
```

### 2. **Executar Script Automatizado**
```bash
# Tornar executável (se necessário)
chmod +x deploy_gcp.sh

# Executar deploy
./deploy_gcp.sh
```

### 3. **Verificar Deploy**
```bash
# O script mostrará a URL automaticamente
# Testar manualmente:
curl https://stratus-ia-xxxxx-uc.a.run.app/health
```

## 🔧 Configuração Manual (Alternativa)

Se preferir fazer manualmente:

```bash
# 1. Configurar projeto
gcloud config set project 7bee-ai

# 2. Habilitar APIs
gcloud services enable cloudbuild.googleapis.com run.googleapis.com secretmanager.googleapis.com containerregistry.googleapis.com

# 3. Criar secrets
echo -n "$JWT_SECRET" | gcloud secrets create jwt-secret --data-file=-
echo -n "$OPENAI_API_KEY" | gcloud secrets create openai-api-key --data-file=-

# 4. Build e push
docker build -t gcr.io/7bee-ai/stratus-ia:v1 .
docker push gcr.io/7bee-ai/stratus-ia:v1

# 5. Deploy
gcloud run deploy stratus-ia \
    --image gcr.io/7bee-ai/stratus-ia:v1 \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --port 8000 \
    --set-env-vars="ENVIRONMENT=production" \
    --set-secrets="JWT_SECRET=jwt-secret:latest" \
    --set-secrets="OPENAI_API_KEY=openai-api-key:latest"
```

## 📋 Checklist Pré-Deploy

- [ ] Conta Google Cloud ativa
- [ ] Projeto `7bee-ai` criado
- [ ] Billing habilitado
- [ ] `gcloud` CLI instalado e logado
- [ ] `docker` instalado
- [ ] `OPENAI_API_KEY` configurada
- [ ] `JWT_SECRET` configurado (ou será gerado automaticamente)

## 🚨 Problemas Comuns

### **Erro: Projeto não existe**
```bash
# Criar projeto no Console do Google Cloud
# Ou usar projeto existente alterando PROJECT_ID no script
```

### **Erro: Permissão negada**
```bash
gcloud auth login
gcloud auth application-default login
```

### **Erro: API não habilitada**
```bash
# O script habilita automaticamente
# Ou manualmente:
gcloud services enable [API_NAME]
```

## 📊 Após o Deploy

- **URL:** `https://stratus-ia-xxxxx-uc.a.run.app`
- **Health:** `https://stratus-ia-xxxxx-uc.a.run.app/health`
- **Docs:** `https://stratus-ia-xxxxx-uc.a.run.app/docs`

## 🔄 Atualizações

```bash
# Para nova versão, apenas execute novamente:
./deploy_gcp.sh
```

---

**⚡ Deploy em menos de 5 minutos!** 