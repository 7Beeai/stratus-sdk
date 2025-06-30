# Implementação será adicionada conforme especificação detalhada. 

import uuid
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
from datetime import datetime, timedelta
import jwt
import bcrypt

class StratusAuthenticationSystem:
    """Sistema de autenticação JWT para Stratus.IA (versão simples para testes/N8N)"""
    def __init__(self, jwt_secret: str, jwt_algorithm: str = "HS256", jwt_expiration: int = 86400, redis_client=None):
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm
        self.jwt_expiration = jwt_expiration
        self.security = HTTPBearer()
        # Usuários em memória (para testes e integração simples)
        self.users: Dict[str, Dict[str, Any]] = {}
        self.passwords: Dict[str, str] = {}  # user_id -> hash

    async def register_user(self, user_data) -> Dict[str, str]:
        # Verifica se email já existe
        for user in self.users.values():
            if user['email'] == user_data.email:
                raise HTTPException(status_code=400, detail="Email já está em uso")
        user_id = str(uuid.uuid4())
        password_hash = self._hash_password(user_data.password)
        self.users[user_id] = {
            "user_id": user_id,
            "name": user_data.name,
            "email": user_data.email,
            "role": user_data.role.value,
            "licenses": user_data.licenses,
            "experience_level": user_data.experience_level,
            "created_at": datetime.utcnow().isoformat()
        }
        self.passwords[user_id] = password_hash
        token = self._generate_token(user_id, user_data.role.value)
        return {"access_token": token, "token_type": "bearer", "user_id": user_id, "message": "Usuário registrado com sucesso"}

    async def login_user(self, credentials) -> Dict[str, str]:
        # Busca usuário por email
        user = None
        for u in self.users.values():
            if u['email'] == credentials.email:
                user = u
                break
        if not user:
            raise HTTPException(status_code=401, detail="Credenciais inválidas")
        user_id = user['user_id']
        password_hash = self.passwords.get(user_id)
        if not password_hash or not self._verify_password(credentials.password, password_hash):
            raise HTTPException(status_code=401, detail="Credenciais inválidas")
        token = self._generate_token(user_id, user['role'])
        return {"access_token": token, "token_type": "bearer", "user_id": user_id, "role": user['role'], "message": "Login realizado com sucesso"}

    async def refresh_token(self, user_id: str) -> Dict[str, str]:
        user = self.users.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        token = self._generate_token(user_id, user['role'])
        return {"access_token": token, "token_type": "bearer", "message": "Token renovado com sucesso"}

    async def logout_user(self, user_id: str) -> Dict[str, str]:
        # Apenas retorna sucesso (não há blacklist em memória)
        return {"message": "Logout realizado com sucesso"}

    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> dict:
        try:
            payload = jwt.decode(credentials.credentials, self.jwt_secret, algorithms=[self.jwt_algorithm])
            user_id = payload.get("sub")
            if not user_id or user_id not in self.users:
                raise HTTPException(status_code=401, detail="Token inválido")
            user = self.users[user_id]
            return user
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expirado")
        except Exception:
            raise HTTPException(status_code=401, detail="Token inválido")

    async def require_admin(self, current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Acesso negado: permissões de administrador necessárias")
        return current_user

    def _generate_token(self, user_id: str, role: str) -> str:
        payload = {
            "sub": user_id,
            "role": role,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(seconds=self.jwt_expiration)
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

    def _hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def _verify_password(self, password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')) 