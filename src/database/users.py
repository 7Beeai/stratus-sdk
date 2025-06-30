"""
User Context Storage para Stratus.IA
Armazenamento de contexto do usuário com cache e operações completas
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from .base import UserProfile, UserRole
from .integration import StratusPostgreSQLIntegration
from src.utils.logging import get_logger


class StratusUserContextStorage:
    """Armazenamento de contexto do usuário"""
    
    def __init__(self, db_integration: StratusPostgreSQLIntegration):
        self.logger = get_logger()
        self.db = db_integration
        
        # Cache de contextos ativos
        self.active_contexts = {}
        
        # Configurações
        self.context_cache_ttl = timedelta(minutes=30)
    
    async def create_user(self, user_profile: UserProfile) -> bool:
        """Cria novo usuário"""
        
        try:
            async with self.db.get_session() as session:
                insert_query = """
                INSERT INTO users 
                (user_id, name, email, role, licenses, experience_level, 
                 preferred_language, timezone, preferences, created_at, last_active)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """
                
                await session.execute(
                    insert_query,
                    user_profile.user_id, user_profile.name, user_profile.email,
                    user_profile.role.value, json.dumps(user_profile.licenses),
                    user_profile.experience_level, user_profile.preferred_language,
                    user_profile.timezone, json.dumps(user_profile.preferences),
                    user_profile.created_at, user_profile.last_active
                )
            
            # Adiciona ao cache
            self.active_contexts[user_profile.user_id] = user_profile
            
            self.logger._log_info(f"Created user {user_profile.user_id}")
            
            return True
            
        except Exception as e:
            self.logger._log_error(f"Failed to create user: {str(e)}")
            return False
    
    async def get_user(self, user_id: str) -> Optional[UserProfile]:
        """Obtém perfil do usuário"""
        
        try:
            # Verifica cache primeiro
            if user_id in self.active_contexts:
                return self.active_contexts[user_id]
            
            # Busca no banco
            query = "SELECT * FROM users WHERE user_id = $1 AND is_active = true"
            results = await self.db.execute_query(query, {"$1": user_id})
            
            if not results:
                return None
            
            row = results[0]
            user_profile = UserProfile(
                user_id=row['user_id'],
                name=row['name'],
                email=row['email'],
                role=UserRole(row['role']),
                licenses=json.loads(row['licenses']) if row['licenses'] else [],
                experience_level=row['experience_level'],
                preferred_language=row['preferred_language'],
                timezone=row['timezone'],
                preferences=json.loads(row['preferences']) if row['preferences'] else {},
                created_at=row['created_at'],
                last_active=row['last_active']
            )
            
            # Adiciona ao cache
            self.active_contexts[user_id] = user_profile
            
            return user_profile
            
        except Exception as e:
            self.logger._log_error(f"Failed to get user: {str(e)}")
            return None
    
    async def update_user(
        self, 
        user_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Atualiza dados do usuário"""
        
        try:
            # Prepara campos para atualização
            set_clauses = []
            params = []
            param_count = 0
            
            allowed_fields = {
                'name', 'email', 'role', 'licenses', 'experience_level',
                'preferred_language', 'timezone', 'preferences'
            }
            
            for field, value in updates.items():
                if field in allowed_fields:
                    param_count += 1
                    set_clauses.append(f"{field} = ${param_count}")
                    
                    # Serializa JSON se necessário
                    if field in ['licenses', 'preferences']:
                        params.append(json.dumps(value))
                    elif field == 'role':
                        params.append(value.value if isinstance(value, UserRole) else value)
                    else:
                        params.append(value)
            
            if not set_clauses:
                return True
            
            # Adiciona timestamp de atualização
            param_count += 1
            set_clauses.append(f"last_active = ${param_count}")
            params.append(datetime.now())
            
            # ID do usuário
            param_count += 1
            params.append(user_id)
            
            query = f"""
            UPDATE users 
            SET {', '.join(set_clauses)}
            WHERE user_id = ${param_count}
            """
            
            await self.db.execute_query(
                query,
                dict(zip([f"${i+1}" for i in range(len(params))], params))
            )
            
            # Remove do cache para forçar reload
            if user_id in self.active_contexts:
                del self.active_contexts[user_id]
            
            return True
            
        except Exception as e:
            self.logger._log_error(f"Failed to update user: {str(e)}")
            return False
    
    async def update_last_active(self, user_id: str) -> bool:
        """Atualiza timestamp de última atividade"""
        
        try:
            query = """
            UPDATE users 
            SET last_active = NOW()
            WHERE user_id = $1
            """
            
            await self.db.execute_query(query, {"$1": user_id})
            
            # Atualiza cache
            if user_id in self.active_contexts:
                self.active_contexts[user_id].last_active = datetime.now()
            
            return True
            
        except Exception as e:
            self.logger._log_error(f"Failed to update last active: {str(e)}")
            return False
    
    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Obtém preferências do usuário"""
        
        try:
            user = await self.get_user(user_id)
            return user.preferences if user else {}
            
        except Exception as e:
            self.logger._log_error(f"Failed to get user preferences: {str(e)}")
            return {}
    
    async def update_user_preferences(
        self, 
        user_id: str, 
        preferences: Dict[str, Any]
    ) -> bool:
        """Atualiza preferências do usuário"""
        
        try:
            # Obtém preferências atuais
            current_prefs = await self.get_user_preferences(user_id)
            
            # Merge com novas preferências
            updated_prefs = {**current_prefs, **preferences}
            
            # Atualiza no banco
            return await self.update_user(user_id, {"preferences": updated_prefs})
            
        except Exception as e:
            self.logger._log_error(f"Failed to update user preferences: {str(e)}")
            return False
    
    async def get_users_by_role(self, role: UserRole) -> List[UserProfile]:
        """Obtém usuários por função"""
        
        try:
            query = """
            SELECT * FROM users 
            WHERE role = $1 AND is_active = true
            ORDER BY last_active DESC
            """
            
            results = await self.db.execute_query(query, {"$1": role.value})
            
            users = []
            for row in results:
                user_profile = UserProfile(
                    user_id=row['user_id'],
                    name=row['name'],
                    email=row['email'],
                    role=UserRole(row['role']),
                    licenses=json.loads(row['licenses']) if row['licenses'] else [],
                    experience_level=row['experience_level'],
                    preferred_language=row['preferred_language'],
                    timezone=row['timezone'],
                    preferences=json.loads(row['preferences']) if row['preferences'] else {},
                    created_at=row['created_at'],
                    last_active=row['last_active']
                )
                users.append(user_profile)
            
            return users
            
        except Exception as e:
            self.logger._log_error(f"Failed to get users by role: {str(e)}")
            return []
    
    async def deactivate_user(self, user_id: str) -> bool:
        """Desativa usuário"""
        
        try:
            query = """
            UPDATE users 
            SET is_active = false, last_active = NOW()
            WHERE user_id = $1
            """
            
            await self.db.execute_query(query, {"$1": user_id})
            
            # Remove do cache
            if user_id in self.active_contexts:
                del self.active_contexts[user_id]
            
            return True
            
        except Exception as e:
            self.logger._log_error(f"Failed to deactivate user: {str(e)}")
            return False
    
    async def get_user_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas de usuários"""
        
        try:
            stats_query = """
            SELECT 
                role,
                COUNT(*) as count,
                COUNT(CASE WHEN last_active > NOW() - INTERVAL '24 hours' THEN 1 END) as active_24h,
                COUNT(CASE WHEN last_active > NOW() - INTERVAL '7 days' THEN 1 END) as active_7d
            FROM users 
            WHERE is_active = true
            GROUP BY role
            """
            
            results = await self.db.execute_query(stats_query)
            
            stats = {
                "total_users": 0,
                "active_24h": 0,
                "active_7d": 0,
                "by_role": {},
                "cache_size": len(self.active_contexts)
            }
            
            for row in results:
                role = row['role']
                count = row['count']
                active_24h = row['active_24h']
                active_7d = row['active_7d']
                
                stats["by_role"][role] = {
                    "total": count,
                    "active_24h": active_24h,
                    "active_7d": active_7d
                }
                
                stats["total_users"] += count
                stats["active_24h"] += active_24h
                stats["active_7d"] += active_7d
            
            return stats
            
        except Exception as e:
            self.logger._log_error(f"Failed to get user stats: {str(e)}")
            return {"error": str(e)} 