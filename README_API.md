# Stratus.IA API

API FastAPI para o sistema de assistente de aviação com IA, desenvolvida para integração com N8N e outros sistemas.

## 🚀 Características

- **FastAPI** - Framework moderno e rápido
- **Autenticação JWT** - Sistema seguro de autenticação
- **Health Checks** - Monitoramento de saúde do sistema
- **Métricas Prometheus** - Observabilidade completa
- **Rate Limiting** - Proteção contra abuso
- **Logging Estruturado** - Logs organizados e rastreáveis
- **Pronto para N8N** - Endpoints REST simples e claros

## 📋 Endpoints Disponíveis

### 🔐 Autenticação
- `POST /auth/register` - Registro de usuário
- `POST /auth/login` - Login de usuário
- `POST /auth/refresh` - Renovação de token
- `POST /auth/logout` - Logout

### 💬 Chat
- `POST /chat` - Envio de mensagem para o assistente

### 🏥 Monitoramento
- `GET /health` - Status de saúde do sistema
- `GET /metrics` - Métricas Prometheus
- `GET /info` - Informações do sistema
- `GET /test` - Teste simples

## 🛠️ Instalação

### 1. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 2. Configurar Variáveis de Ambiente
```bash
# Copie o arquivo de exemplo
cp env.example .env

# Edite as variáveis necessárias
export JWT_SECRET="sua-chave-secreta-aqui"
export OPENAI_API_KEY="sua-chave-openai"
export ENVIRONMENT="development"
export DEBUG="true"
```

### 3. Iniciar a API
```bash
# Opção 1: Usando o script
python start_api.py

# Opção 2: Usando uvicorn diretamente
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

## 📖 Uso da API

### 1. Registro de Usuário
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "João Silva",
    "email": "joao@exemplo.com",
    "password": "Senha123!",
    "role": "pilot",
    "licenses": ["PP", "PC"],
    "experience_level": "Intermediário"
  }'
```

### 2. Login
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "joao@exemplo.com",
    "password": "Senha123!"
  }'
```

### 3. Chat com Autenticação
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Authorization: Bearer SEU_TOKEN_AQUI" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Como está o tempo para voo hoje?",
    "message_type": "question",
    "context": {"airport": "SBSP"}
  }'
```

### 4. Health Check
```bash
curl "http://localhost:8000/health"
```

## 🔧 Configuração para N8N

### 1. Configuração do N8N
No N8N, configure um nó HTTP Request com:

**URL Base:** `http://localhost:8000` (ou sua URL de produção)

**Headers:**
```
Content-Type: application/json
Authorization: Bearer {{$json.access_token}}
```

### 2. Fluxo de Autenticação
1. **Login Node:**
   - Method: POST
   - URL: `/auth/login`
   - Body: 
   ```json
   {
     "email": "seu-email@exemplo.com",
     "password": "sua-senha"
   }
   ```

2. **Chat Node:**
   - Method: POST
   - URL: `/chat`
   - Headers: `Authorization: Bearer {{$json.access_token}}`
   - Body:
   ```json
   {
     "message": "{{$json.message}}",
     "message_type": "question"
   }
   ```

### 3. Exemplo de Workflow N8N
```json
{
  "nodes": [
    {
      "name": "Login",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "http://localhost:8000/auth/login",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "email",
              "value": "admin@stratus.ia"
            },
            {
              "name": "password", 
              "value": "Admin123!"
            }
          ]
        }
      }
    },
    {
      "name": "Chat",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "http://localhost:8000/chat",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "Authorization",
              "value": "Bearer {{$json.access_token}}"
            }
          ]
        },
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "message",
              "value": "Como está o tempo para voo?"
            },
            {
              "name": "message_type",
              "value": "question"
            }
          ]
        }
      }
    }
  ]
}
```

## 🧪 Testes

### Executar Testes Automatizados
```bash
python test_api.py
```

### Testes Manuais
1. **Health Check:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Info:**
   ```bash
   curl http://localhost:8000/info
   ```

3. **Métricas:**
   ```bash
   curl http://localhost:8000/metrics
   ```

## 📊 Monitoramento

### Health Check
O endpoint `/health` retorna:
- Status geral do sistema
- Status de cada componente
- Métricas de uptime
- Versão da aplicação

### Métricas Prometheus
O endpoint `/metrics` expõe métricas como:
- Total de requisições
- Duração das requisições
- Usuários ativos
- Respostas dos agentes
- Violações de segurança

## 🔒 Segurança

### Autenticação JWT
- Tokens com expiração configurável
- Hash de senha com bcrypt
- Validação de email e senha
- Rate limiting por endpoint

### Validação de Dados
- Validação de email
- Requisitos de senha forte
- Validação de roles de usuário
- Sanitização de entrada

## 🚀 Deploy

### Desenvolvimento Local
```bash
python start_api.py
```

### Produção com Docker
```bash
docker build -t stratus-api .
docker run -p 8000:8000 stratus-api
```

### Google Cloud Run
```bash
gcloud run deploy stratus-api \
  --image gcr.io/PROJECT_ID/stratus-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## 📝 Logs

A API utiliza logging estruturado com:
- Nível de log configurável
- Formato JSON para produção
- Contexto de requisição
- Métricas de performance

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.

## 🆘 Suporte

Para suporte e dúvidas:
- Abra uma issue no GitHub
- Consulte a documentação da API em `/docs` (quando DEBUG=true)
- Entre em contato com a equipe de desenvolvimento 