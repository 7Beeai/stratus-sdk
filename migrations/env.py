import sys
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, MetaData, Table, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index, Float
from sqlalchemy.dialects.postgresql import JSONB
from alembic import context
from datetime import datetime

# Adiciona src ao sys.path para imports absolutos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# Configuração do Alembic
config = context.config

# Configura logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Cria metadata diretamente (sem instanciar StratusPostgreSQLIntegration)
metadata = MetaData()

# Define tabelas manualmente para migração
users_table = Table(
    'users',
    metadata,
    Column('user_id', String(36), primary_key=True),
    Column('name', String(255), nullable=False),
    Column('email', String(255), unique=True),
    Column('role', String(50), nullable=False),
    Column('licenses', JSONB),
    Column('experience_level', String(50)),
    Column('preferred_language', String(10), default='pt-BR'),
    Column('timezone', String(50), default='America/Sao_Paulo'),
    Column('preferences', JSONB),
    Column('created_at', DateTime, default=datetime.now),
    Column('last_active', DateTime, default=datetime.now),
    Column('is_active', Boolean, default=True),
    Index('idx_users_email', 'email'),
    Index('idx_users_role', 'role'),
    Index('idx_users_last_active', 'last_active')
)

conversations_table = Table(
    'conversations',
    metadata,
    Column('conversation_id', String(36), primary_key=True),
    Column('user_id', String(36), ForeignKey('users.user_id'), nullable=False),
    Column('title', String(500), nullable=False),
    Column('status', String(20), default='active'),
    Column('context', JSONB),
    Column('summary', Text),
    Column('started_at', DateTime, default=datetime.now),
    Column('last_message_at', DateTime, default=datetime.now),
    Column('message_count', Integer, default=0),
    Column('total_tokens', Integer, default=0),
    Index('idx_conversations_user_id', 'user_id'),
    Index('idx_conversations_status', 'status'),
    Index('idx_conversations_last_message', 'last_message_at')
)

messages_table = Table(
    'messages',
    metadata,
    Column('message_id', String(36), primary_key=True),
    Column('conversation_id', String(36), ForeignKey('conversations.conversation_id'), nullable=False),
    Column('user_id', String(36), ForeignKey('users.user_id'), nullable=False),
    Column('agent_name', String(100)),
    Column('message_type', String(20), nullable=False),
    Column('content', Text, nullable=False),
    Column('metadata', JSONB),
    Column('timestamp', DateTime, default=datetime.now),
    Column('tokens_used', Integer),
    Column('response_time', Float),
    Index('idx_messages_conversation_id', 'conversation_id'),
    Index('idx_messages_user_id', 'user_id'),
    Index('idx_messages_timestamp', 'timestamp'),
    Index('idx_messages_type', 'message_type')
)

memory_table = Table(
    'memory_entries',
    metadata,
    Column('memory_id', String(36), primary_key=True),
    Column('user_id', String(36), ForeignKey('users.user_id'), nullable=False),
    Column('correlation_id', String(36), nullable=False),
    Column('memory_type', String(20), nullable=False),
    Column('key', String(255), nullable=False),
    Column('value', JSONB, nullable=False),
    Column('context', JSONB),
    Column('importance_score', Float, default=0.5),
    Column('access_count', Integer, default=0),
    Column('created_at', DateTime, default=datetime.now),
    Column('last_accessed', DateTime, default=datetime.now),
    Column('expires_at', DateTime),
    Index('idx_memory_user_id', 'user_id'),
    Index('idx_memory_correlation_id', 'correlation_id'),
    Index('idx_memory_type', 'memory_type'),
    Index('idx_memory_key', 'key'),
    Index('idx_memory_importance', 'importance_score'),
    Index('idx_memory_expires', 'expires_at')
)

audit_table = Table(
    'audit_log',
    metadata,
    Column('audit_id', String(36), primary_key=True),
    Column('user_id', String(36)),
    Column('action', String(100), nullable=False),
    Column('table_name', String(50)),
    Column('record_id', String(36)),
    Column('old_values', JSONB),
    Column('new_values', JSONB),
    Column('timestamp', DateTime, default=datetime.now),
    Column('ip_address', String(45)),
    Column('user_agent', String(500)),
    Index('idx_audit_user_id', 'user_id'),
    Index('idx_audit_action', 'action'),
    Index('idx_audit_timestamp', 'timestamp')
)

def get_url():
    return os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:password@localhost:5432/stratus_ia")

def run_migrations_offline():
    url = get_url()
    context.configure(
        url=url,
        target_metadata=metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
