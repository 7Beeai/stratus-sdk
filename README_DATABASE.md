# Sistema de Banco de Dados Stratus.IA

## 📋 Visão Geral

O sistema de banco de dados do Stratus.IA é uma solução robusta e escalável para gerenciar dados de usuários, memórias, conversas e auditoria na plataforma de IA para aviação civil brasileira.

## 🏗️ Arquitetura

### Componentes Principais

1. **Integração PostgreSQL** (`src/database/integration.py`)
   - Conexão assíncrona com PostgreSQL
   - Pool de conexões configurável
   - Tratamento robusto de erros
   - Métricas de performance

2. **Gerenciador de Memória** (`src/database/memory.py`)
   - Armazenamento inteligente de memórias
   - Sistema de cache em memória
   - Expiração automática
   - Busca por relevância

3. **Histórico de Conversas** (`src/database/conversations.py`)
   - Armazenamento completo de conversas
   - Metadados de mensagens
   - Estatísticas de uso
   - Compressão de histórico

4. **Gerenciamento de Usuários** (`src/database/users.py`)
   - Perfis de usuários especializados
   - Licenças e certificações
   - Preferências personalizadas
   - Controle de acesso

5. **Sistema de Auditoria** (`src/database/system.py`)
   - Log de todas as operações
   - Rastreamento de mudanças
   - Compliance e segurança
   - Relatórios automáticos

## 🚀 Instalação e Configuração

### Pré-requisitos

```bash
# Instalar dependências
pip install sqlalchemy asyncpg psycopg2-binary alembic

# Configurar variáveis de ambiente
export DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/stratus_ia"
export OPENAI_API_KEY="sua-api-key-aqui"
```

### Configuração do Banco

```bash
# Inicializar Alembic (já feito)
alembic init migrations

# Gerar migração inicial
alembic revision --autogenerate -m "Initial migration"

# Executar migração
alembic upgrade head
```

## 📊 Estrutura do Banco

### Tabelas Principais

#### `users`
- `user_id` (UUID, PK)
- `name` (VARCHAR)
- `email` (VARCHAR, UNIQUE)
- `role` (ENUM: pilot, instructor, mechanic, etc.)
- `licenses` (JSONB)
- `experience_level` (VARCHAR)
- `preferences` (JSONB)
- `created_at`, `last_active` (TIMESTAMP)

#### `conversations`
- `conversation_id` (UUID, PK)
- `user_id` (UUID, FK)
- `title` (VARCHAR)
- `status` (ENUM: active, archived, deleted)
- `context` (JSONB)
- `summary` (TEXT)
- `message_count`, `total_tokens` (INTEGER)

#### `messages`
- `message_id` (UUID, PK)
- `conversation_id` (UUID, FK)
- `user_id` (UUID, FK)
- `agent_name` (VARCHAR)
- `message_type` (ENUM: user_input, agent_response, system)
- `content` (TEXT)
- `metadata` (JSONB)
- `tokens_used`, `response_time` (INTEGER/FLOAT)

#### `memory_entries`
- `memory_id` (UUID, PK)
- `user_id` (UUID, FK)
- `memory_type` (ENUM: short_term, medium_term, long_term, critical)
- `key` (VARCHAR)
- `value` (JSONB)
- `importance_score` (FLOAT)
- `access_count` (INTEGER)
- `expires_at` (TIMESTAMP)

#### `audit_log`
- `audit_id` (UUID, PK)
- `user_id` (UUID)
- `action` (VARCHAR)
- `table_name` (VARCHAR)
- `old_values`, `new_values` (JSONB)
- `timestamp` (TIMESTAMP)
- `ip_address`, `user_agent` (VARCHAR)

## 🔧 Uso da API

### Exemplo de Uso Básico

```python
import asyncio
from src.database.integration import StratusPostgreSQLIntegration
from src.database.memory import MemoryManager
from src.database.conversations import ConversationManager
from src.database.users import UserManager

async def exemplo_uso():
    # Inicializar sistema
    db = StratusPostgreSQLIntegration()
    memory_mgr = MemoryManager(db)
    conv_mgr = ConversationManager(db)
    user_mgr = UserManager(db)
    
    # Criar usuário
    user = await user_mgr.create_user(
        name="João Silva",
        email="joao@aviacao.com",
        role="pilot",
        licenses=["PP", "PC", "IFR"]
    )
    
    # Armazenar memória
    await memory_mgr.store_memory(
        user_id=user.user_id,
        key="preferred_aircraft",
        value="Cessna 172",
        memory_type="long_term",
        importance_score=0.8
    )
    
    # Criar conversa
    conv = await conv_mgr.create_conversation(
        user_id=user.user_id,
        title="Consulta meteorológica"
    )
    
    # Adicionar mensagem
    await conv_mgr.add_message(
        conversation_id=conv.conversation_id,
        user_id=user.user_id,
        content="Qual o METAR de SBGR?",
        message_type="user_input"
    )
```

## 🧪 Testes e Demonstração

### Executar Demonstração

```bash
# Demonstração completa do sistema
python demo_database.py
```

### Testes Unitários

```bash
# Executar testes específicos
python -m pytest tests/test_database/ -v
```

## 📈 Métricas e Monitoramento

### Métricas Disponíveis

- **Performance**: Tempo de resposta, throughput
- **Uso**: Usuários ativos, conversas por dia
- **Qualidade**: Taxa de erro, disponibilidade
- **Negócio**: Engajamento, retenção

### Logs Estruturados

Todos os logs seguem formato JSON estruturado:
```json
{
  "timestamp": "2025-06-30T20:04:38.093286+00:00",
  "level": "INFO",
  "log_type": "DATABASE",
  "trace_id": "bbf3f197-57f9-4686-962a-62bdd4d3853c",
  "message": "User created successfully",
  "module": "stratus_ia",
  "function": "create_user",
  "line": 45,
  "process_id": 60497,
  "thread_id": 8582078208,
  "metrics": {
    "operation_duration_ms": 125,
    "memory_usage_mb": 45.2
  }
}
```

## 🔒 Segurança

### Medidas Implementadas

- **Criptografia**: Dados sensíveis criptografados
- **Auditoria**: Log completo de todas as operações
- **Validação**: Validação rigorosa de entrada
- **Sanitização**: Prevenção de SQL injection
- **Controle de Acesso**: Baseado em roles

### Compliance

- **LGPD**: Conformidade com lei brasileira
- **ANAC**: Regulamentações de aviação
- **ISO 27001**: Padrões de segurança

## 🚀 Deploy

### Google Cloud Run

```bash
# Build da imagem
docker build -t stratus-ia-database .

# Deploy
gcloud run deploy stratus-ia-database \
  --image gcr.io/PROJECT_ID/stratus-ia-database \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Variáveis de Ambiente

```bash
# Produção
DATABASE_URL=postgresql+asyncpg://user:pass@/dbname?host=/cloudsql/PROJECT_ID:REGION:INSTANCE
OPENAI_API_KEY=sk-...
LOG_LEVEL=INFO
ENVIRONMENT=production

# Desenvolvimento
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/stratus_ia
OPENAI_API_KEY=sk-...
LOG_LEVEL=DEBUG
ENVIRONMENT=development
```

## 📚 Documentação Adicional

- [Arquitetura Detalhada](docs/architecture.md)
- [Guia de Migração](docs/migration_guide.md)
- [API Reference](docs/api_reference.md)
- [Troubleshooting](docs/troubleshooting.md)

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature
3. Implemente com testes
4. Siga os padrões de código
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob licença MIT. Veja [LICENSE](LICENSE) para detalhes.

---

**Stratus.IA** - Sistema de IA para Aviação Civil Brasileira 🛩️ 