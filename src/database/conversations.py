"""
Conversation History para Stratus.IA
Gerenciador de histórico de conversas completo com sumarização automática
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from .base import MessageType, ConversationStatus, ConversationMessage, ConversationSession
from .integration import StratusPostgreSQLIntegration
from src.utils.logging import get_logger


class StratusConversationHistory:
    """Gerenciador de histórico de conversas"""
    
    def __init__(self, db_integration: StratusPostgreSQLIntegration):
        self.logger = get_logger()
        self.db = db_integration
        
        # Cache de conversas ativas
        self.active_conversations = {}
        
        # Configurações
        self.max_messages_per_conversation = 100  # Limite de 100 mensagens por conversa
        self.conversation_timeout = timedelta(hours=24)
        
        # Agente de sumarização (mock para demo)
        self.summarizer_agent = None  # Será inicializado quando necessário
    
    async def create_conversation(
        self, 
        user_id: str, 
        title: str,
        initial_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Cria nova conversa"""
        
        try:
            conversation_id = str(uuid.uuid4())
            
            conversation = ConversationSession(
                conversation_id=conversation_id,
                user_id=user_id,
                title=title,
                status=ConversationStatus.ACTIVE,
                context=initial_context or {}
            )
            
            # Armazena no banco
            async with self.db.get_session() as session:
                insert_query = """
                INSERT INTO conversations 
                (conversation_id, user_id, title, status, context, started_at, last_message_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """
                
                await session.execute(
                    insert_query,
                    conversation_id, user_id, title, conversation.status.value,
                    json.dumps(conversation.context), conversation.started_at,
                    conversation.last_message_at
                )
            
            # Adiciona ao cache
            self.active_conversations[conversation_id] = conversation
            
            self.logger._log_info(f"Created conversation {conversation_id} for user {user_id}")
            
            return conversation_id
            
        except Exception as e:
            self.logger._log_error(f"Failed to create conversation: {str(e)}")
            raise
    
    async def add_message(
        self, 
        conversation_id: str,
        user_id: str,
        content: str,
        message_type: MessageType,
        agent_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tokens_used: Optional[int] = None,
        response_time: Optional[float] = None
    ) -> str:
        """Adiciona mensagem à conversa"""
        
        try:
            # Verifica limite de mensagens por conversa
            current_message_count = await self._get_conversation_message_count(conversation_id)
            if current_message_count >= self.max_messages_per_conversation:
                self.logger._log_warning(
                    f"Conversation {conversation_id} reached message limit ({self.max_messages_per_conversation})"
                )
                # Cria nova conversa automaticamente
                conversation = await self.get_conversation(conversation_id)
                if conversation:
                    new_conversation_id = await self.create_conversation(
                        user_id=user_id,
                        title=f"{conversation.title} (continuação)",
                        initial_context=conversation.context
                    )
                    self.logger._log_info(f"Created new conversation {new_conversation_id} due to message limit")
                    conversation_id = new_conversation_id
            
            message_id = str(uuid.uuid4())
            
            message = ConversationMessage(
                message_id=message_id,
                conversation_id=conversation_id,
                user_id=user_id,
                agent_name=agent_name,
                message_type=message_type,
                content=content,
                metadata=metadata or {},
                tokens_used=tokens_used,
                response_time=response_time
            )
            
            # Armazena mensagem
            async with self.db.get_session() as session:
                insert_query = """
                INSERT INTO messages 
                (message_id, conversation_id, user_id, agent_name, message_type, 
                 content, metadata, timestamp, tokens_used, response_time)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """
                
                await session.execute(
                    insert_query,
                    message_id, conversation_id, user_id, agent_name,
                    message_type.value, content, json.dumps(message.metadata),
                    message.timestamp, tokens_used, response_time
                )
            
            # Atualiza conversa
            await self._update_conversation_stats(conversation_id, tokens_used or 0)
            
            # Verifica se precisa sumarizar
            await self._check_summarization_needed(conversation_id)
            
            self.logger._log_info(
                f"Added message to conversation {conversation_id}",
                extra={
                    "message_id": message_id,
                    "message_type": message_type.value,
                    "agent_name": agent_name
                }
            )
            
            return message_id
            
        except Exception as e:
            self.logger._log_error(f"Failed to add message: {str(e)}")
            raise
    
    async def get_conversation(self, conversation_id: str) -> Optional[ConversationSession]:
        """Obtém conversa por ID"""
        
        try:
            # Verifica cache primeiro
            if conversation_id in self.active_conversations:
                return self.active_conversations[conversation_id]
            
            # Busca no banco
            query = "SELECT * FROM conversations WHERE conversation_id = $1"
            results = await self.db.execute_query(query, {"$1": conversation_id})
            
            if not results:
                return None
            
            row = results[0]
            conversation = ConversationSession(
                conversation_id=row['conversation_id'],
                user_id=row['user_id'],
                title=row['title'],
                status=ConversationStatus(row['status']),
                context=json.loads(row['context']) if row['context'] else {},
                summary=row['summary'],
                started_at=row['started_at'],
                last_message_at=row['last_message_at'],
                message_count=row['message_count'],
                total_tokens=row['total_tokens']
            )
            
            # Adiciona ao cache
            self.active_conversations[conversation_id] = conversation
            
            return conversation
            
        except Exception as e:
            self.logger._log_error(f"Failed to get conversation: {str(e)}")
            return None
    
    async def get_conversation_messages(
        self, 
        conversation_id: str,
        limit: int = 50,
        offset: int = 0,
        message_types: Optional[List[MessageType]] = None
    ) -> List[ConversationMessage]:
        """Obtém mensagens da conversa"""
        
        try:
            conditions = ["conversation_id = $1"]
            params = [conversation_id]
            param_count = 1
            
            if message_types:
                type_values = [mt.value for mt in message_types]
                param_count += 1
                conditions.append(f"message_type = ANY(${param_count})")
                params.append(type_values)
            
            query = f"""
            SELECT * FROM messages 
            WHERE {' AND '.join(conditions)}
            ORDER BY timestamp ASC
            LIMIT {limit} OFFSET {offset}
            """
            
            results = await self.db.execute_query(
                query, 
                dict(zip([f"${i+1}" for i in range(len(params))], params))
            )
            
            messages = []
            for row in results:
                message = ConversationMessage(
                    message_id=row['message_id'],
                    conversation_id=row['conversation_id'],
                    user_id=row['user_id'],
                    agent_name=row['agent_name'],
                    message_type=MessageType(row['message_type']),
                    content=row['content'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    timestamp=row['timestamp'],
                    tokens_used=row['tokens_used'],
                    response_time=row['response_time']
                )
                messages.append(message)
            
            return messages
            
        except Exception as e:
            self.logger._log_error(f"Failed to get conversation messages: {str(e)}")
            return []
    
    async def get_user_conversations(
        self, 
        user_id: str,
        status: Optional[ConversationStatus] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[ConversationSession]:
        """Obtém conversas do usuário"""
        
        try:
            conditions = ["user_id = $1"]
            params = [user_id]
            param_count = 1
            
            if status:
                param_count += 1
                conditions.append(f"status = ${param_count}")
                params.append(status.value)
            
            query = f"""
            SELECT * FROM conversations 
            WHERE {' AND '.join(conditions)}
            ORDER BY last_message_at DESC
            LIMIT {limit} OFFSET {offset}
            """
            
            results = await self.db.execute_query(
                query,
                dict(zip([f"${i+1}" for i in range(len(params))], params))
            )
            
            conversations = []
            for row in results:
                conversation = ConversationSession(
                    conversation_id=row['conversation_id'],
                    user_id=row['user_id'],
                    title=row['title'],
                    status=ConversationStatus(row['status']),
                    context=json.loads(row['context']) if row['context'] else {},
                    summary=row['summary'],
                    started_at=row['started_at'],
                    last_message_at=row['last_message_at'],
                    message_count=row['message_count'],
                    total_tokens=row['total_tokens']
                )
                conversations.append(conversation)
            
            return conversations
            
        except Exception as e:
            self.logger._log_error(f"Failed to get user conversations: {str(e)}")
            return []
    
    async def update_conversation_status(
        self, 
        conversation_id: str, 
        status: ConversationStatus
    ) -> bool:
        """Atualiza status da conversa"""
        
        try:
            query = """
            UPDATE conversations 
            SET status = $1, last_message_at = NOW()
            WHERE conversation_id = $2
            """
            
            await self.db.execute_query(query, {"$1": status.value, "$2": conversation_id})
            
            # Atualiza cache
            if conversation_id in self.active_conversations:
                self.active_conversations[conversation_id].status = status
                self.active_conversations[conversation_id].last_message_at = datetime.now()
            
            return True
            
        except Exception as e:
            self.logger._log_error(f"Failed to update conversation status: {str(e)}")
            return False
    
    async def search_conversations(
        self, 
        user_id: str,
        search_term: str,
        limit: int = 10
    ) -> List[ConversationSession]:
        """Busca conversas por termo"""
        
        try:
            query = """
            SELECT DISTINCT c.* FROM conversations c
            LEFT JOIN messages m ON c.conversation_id = m.conversation_id
            WHERE c.user_id = $1 
            AND (c.title ILIKE $2 OR c.summary ILIKE $2 OR m.content ILIKE $2)
            ORDER BY c.last_message_at DESC
            LIMIT $3
            """
            
            search_pattern = f"%{search_term}%"
            results = await self.db.execute_query(
                query, 
                {"$1": user_id, "$2": search_pattern, "$3": limit}
            )
            
            conversations = []
            for row in results:
                conversation = ConversationSession(
                    conversation_id=row['conversation_id'],
                    user_id=row['user_id'],
                    title=row['title'],
                    status=ConversationStatus(row['status']),
                    context=json.loads(row['context']) if row['context'] else {},
                    summary=row['summary'],
                    started_at=row['started_at'],
                    last_message_at=row['last_message_at'],
                    message_count=row['message_count'],
                    total_tokens=row['total_tokens']
                )
                conversations.append(conversation)
            
            return conversations
            
        except Exception as e:
            self.logger._log_error(f"Failed to search conversations: {str(e)}")
            return []
    
    async def _update_conversation_stats(self, conversation_id: str, tokens_used: int):
        """Atualiza estatísticas da conversa"""
        
        try:
            query = """
            UPDATE conversations 
            SET message_count = message_count + 1,
                total_tokens = total_tokens + $1,
                last_message_at = NOW()
            WHERE conversation_id = $2
            """
            
            await self.db.execute_query(query, {"$1": tokens_used, "$2": conversation_id})
            
            # Atualiza cache
            if conversation_id in self.active_conversations:
                conv = self.active_conversations[conversation_id]
                conv.message_count += 1
                conv.total_tokens += tokens_used
                conv.last_message_at = datetime.now()
            
        except Exception as e:
            self.logger._log_error(f"Failed to update conversation stats: {str(e)}")
    
    async def _check_summarization_needed(self, conversation_id: str):
        """Verifica se conversa precisa ser sumarizada"""
        
        try:
            # Conta mensagens
            count_query = """
            SELECT COUNT(*) as count FROM messages 
            WHERE conversation_id = $1
            """
            
            result = await self.db.execute_query(count_query, {"$1": conversation_id})
            message_count = result[0]['count'] if result else 0
            
            # Sumariza a cada 50 mensagens
            if message_count > 0 and message_count % 50 == 0:
                await self._summarize_conversation(conversation_id)
                
        except Exception as e:
            self.logger._log_error(f"Failed to check summarization: {str(e)}")
    
    async def _summarize_conversation(self, conversation_id: str):
        """Cria resumo da conversa"""
        
        try:
            # Obtém últimas 50 mensagens
            messages = await self.get_conversation_messages(
                conversation_id, 
                limit=50
            )
            
            if not messages:
                return
            
            # Prepara conteúdo para sumarização
            conversation_text = []
            for msg in messages:
                role = "Usuário" if msg.message_type == MessageType.USER_INPUT else f"Agente ({msg.agent_name})"
                conversation_text.append(f"{role}: {msg.content}")
            
            text_to_summarize = "\n".join(conversation_text)
            
            # Cria resumo simples (mock para demo)
            summary = f"Conversa com {len(messages)} mensagens. Tópicos principais: {text_to_summarize[:200]}..."
            
            # Atualiza conversa com resumo
            update_query = """
            UPDATE conversations 
            SET summary = $1
            WHERE conversation_id = $2
            """
            
            await self.db.execute_query(update_query, {"$1": summary, "$2": conversation_id})
            
            # Atualiza cache
            if conversation_id in self.active_conversations:
                self.active_conversations[conversation_id].summary = summary
            
            self.logger._log_info(f"Created summary for conversation {conversation_id}")
            
        except Exception as e:
            self.logger._log_error(f"Failed to summarize conversation: {str(e)}")
    
    async def archive_old_conversations(self, days_old: int = 30) -> int:
        """Arquiva conversas antigas"""
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            query = """
            UPDATE conversations 
            SET status = $1
            WHERE last_message_at < $2 
            AND status = $3
            """
            
            await self.db.execute_query(
                query,
                {
                    "$1": ConversationStatus.ARCHIVED.value,
                    "$2": cutoff_date,
                    "$3": ConversationStatus.COMPLETED.value
                }
            )
            
            # Remove do cache
            archived_keys = []
            for conv_id, conv in self.active_conversations.items():
                if (conv.last_message_at < cutoff_date and 
                    conv.status == ConversationStatus.COMPLETED):
                    archived_keys.append(conv_id)
            
            for key in archived_keys:
                del self.active_conversations[key]
            
            self.logger._log_info(f"Archived {len(archived_keys)} old conversations")
            
            return len(archived_keys)
            
        except Exception as e:
            self.logger._log_error(f"Failed to archive conversations: {str(e)}")
            return 0
    
    async def _get_conversation_message_count(self, conversation_id: str) -> int:
        """Obtém o número atual de mensagens em uma conversa"""
        
        try:
            query = """
            SELECT COUNT(*) as count FROM messages 
            WHERE conversation_id = $1
            """
            
            result = await self.db.execute_query(query, {"$1": conversation_id})
            return result[0]['count'] if result else 0
            
        except Exception as e:
            self.logger._log_error(f"Failed to get message count: {str(e)}")
            return 0 