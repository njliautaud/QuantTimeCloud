"""
QuantTime Authentication Module

Handles authentication, authorization, and security for the distributed computing server.
"""

import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
import redis

# Configure logging
logger = logging.getLogger(__name__)

class AuthManager:
    """Authentication and authorization manager"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """Initialize auth manager"""
        self.redis_url = redis_url
        self.redis_client = None
        
        # JWT settings
        self.jwt_secret = self._get_or_create_jwt_secret()
        self.jwt_algorithm = "HS256"
        self.token_expiry_hours = 24
        
        # API key settings
        self.api_keys: Dict[str, Dict[str, Any]] = {}
        
        # Session settings
        self.session_timeout_minutes = 60
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
    def _get_or_create_jwt_secret(self) -> str:
        """Get or create JWT secret key"""
        try:
            # Try to load from environment or file
            import os
            secret = os.getenv("QUANTTIME_JWT_SECRET")
            if secret:
                return secret
            
            # Generate new secret
            secret = secrets.token_urlsafe(64)
            logger.warning("Generated new JWT secret. Consider setting QUANTTIME_JWT_SECRET environment variable.")
            return secret
            
        except Exception as e:
            logger.error(f"Failed to get JWT secret: {e}")
            return secrets.token_urlsafe(64)
    
    async def start(self):
        """Start auth manager"""
        try:
            # Initialize Redis connection
            self.redis_client = redis.Redis.from_url(self.redis_url)
            self.redis_client.ping()
            
            # Load API keys
            await self._load_api_keys()
            
            logger.info("✅ Auth Manager started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Auth Manager: {e}")
            raise
    
    async def stop(self):
        """Stop auth manager"""
        # Clear active sessions
        self.active_sessions.clear()
        logger.info("✅ Auth Manager stopped")
    
    def generate_server_token(self, server_id: str, permissions: list = None) -> str:
        """Generate JWT token for server authentication"""
        try:
            permissions = permissions or ["read", "write", "execute"]
            
            payload = {
                "server_id": server_id,
                "permissions": permissions,
                "issued_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(hours=self.token_expiry_hours)).isoformat(),
                "type": "server_token"
            }
            
            token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
            
            # Store token info in Redis
            if self.redis_client:
                self.redis_client.set(
                    f"auth:token:{server_id}",
                    json.dumps(payload),
                    ex=int(self.token_expiry_hours * 3600)
                )
            
            logger.info(f"Generated server token for: {server_id}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to generate server token: {e}")
            raise
    
    def generate_api_key(self, name: str, permissions: list = None) -> str:
        """Generate API key for external access"""
        try:
            permissions = permissions or ["read"]
            
            api_key = f"qk_{secrets.token_urlsafe(32)}"
            
            key_info = {
                "name": name,
                "permissions": permissions,
                "created_at": datetime.utcnow().isoformat(),
                "last_used": None,
                "usage_count": 0,
                "active": True
            }
            
            self.api_keys[api_key] = key_info
            
            # Store in Redis
            if self.redis_client:
                self.redis_client.set(
                    f"auth:api_key:{api_key}",
                    json.dumps(key_info),
                    ex=86400 * 365  # 1 year expiry
                )
            
            logger.info(f"Generated API key: {name}")
            return api_key
            
        except Exception as e:
            logger.error(f"Failed to generate API key: {e}")
            raise
    
    def authenticate_token(self, token: str) -> bool:
        """Authenticate JWT token"""
        try:
            # Decode and verify token
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Check expiry
            expires_at = datetime.fromisoformat(payload["expires_at"])
            if datetime.utcnow() > expires_at:
                logger.warning("Token expired")
                return False
            
            # Verify token exists in Redis
            if self.redis_client:
                server_id = payload.get("server_id")
                if server_id:
                    stored_payload = self.redis_client.get(f"auth:token:{server_id}")
                    if not stored_payload:
                        logger.warning("Token not found in store")
                        return False
            
            return True
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return False
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return False
        except Exception as e:
            logger.error(f"Token authentication error: {e}")
            return False
    
    def authenticate_api_key(self, api_key: str) -> bool:
        """Authenticate API key"""
        try:
            # Check local cache first
            if api_key in self.api_keys:
                key_info = self.api_keys[api_key]
                if key_info.get("active", False):
                    # Update usage stats
                    key_info["last_used"] = datetime.utcnow().isoformat()
                    key_info["usage_count"] += 1
                    return True
            
            # Check Redis
            if self.redis_client:
                stored_info = self.redis_client.get(f"auth:api_key:{api_key}")
                if stored_info:
                    key_info = json.loads(stored_info)
                    if key_info.get("active", False):
                        # Update usage stats
                        key_info["last_used"] = datetime.utcnow().isoformat()
                        key_info["usage_count"] += 1
                        
                        # Update cache and Redis
                        self.api_keys[api_key] = key_info
                        self.redis_client.set(
                            f"auth:api_key:{api_key}",
                            json.dumps(key_info),
                            ex=86400 * 365
                        )
                        
                        return True
            
            logger.warning(f"Invalid API key used")
            return False
            
        except Exception as e:
            logger.error(f"API key authentication error: {e}")
            return False
    
    def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key"""
        try:
            if api_key in self.api_keys:
                self.api_keys[api_key]["active"] = False
                
                # Update Redis
                if self.redis_client:
                    self.redis_client.set(
                        f"auth:api_key:{api_key}",
                        json.dumps(self.api_keys[api_key]),
                        ex=86400 * 365
                    )
                
                logger.info(f"Revoked API key: {api_key}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to revoke API key: {e}")
            return False
    
    def create_session(self, user_id: str, permissions: list = None) -> str:
        """Create user session"""
        try:
            session_id = secrets.token_urlsafe(32)
            permissions = permissions or ["read"]
            
            session_info = {
                "user_id": user_id,
                "permissions": permissions,
                "created_at": datetime.utcnow().isoformat(),
                "last_activity": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(minutes=self.session_timeout_minutes)).isoformat()
            }
            
            self.active_sessions[session_id] = session_info
            
            # Store in Redis
            if self.redis_client:
                self.redis_client.set(
                    f"auth:session:{session_id}",
                    json.dumps(session_info),
                    ex=int(self.session_timeout_minutes * 60)
                )
            
            logger.info(f"Created session for user: {user_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    def validate_session(self, session_id: str) -> bool:
        """Validate user session"""
        try:
            # Check local cache
            if session_id in self.active_sessions:
                session_info = self.active_sessions[session_id]
                expires_at = datetime.fromisoformat(session_info["expires_at"])
                
                if datetime.utcnow() <= expires_at:
                    # Update last activity
                    session_info["last_activity"] = datetime.utcnow().isoformat()
                    return True
                else:
                    # Session expired
                    del self.active_sessions[session_id]
                    return False
            
            # Check Redis
            if self.redis_client:
                stored_session = self.redis_client.get(f"auth:session:{session_id}")
                if stored_session:
                    session_info = json.loads(stored_session)
                    expires_at = datetime.fromisoformat(session_info["expires_at"])
                    
                    if datetime.utcnow() <= expires_at:
                        # Update last activity
                        session_info["last_activity"] = datetime.utcnow().isoformat()
                        self.active_sessions[session_id] = session_info
                        
                        # Update Redis
                        self.redis_client.set(
                            f"auth:session:{session_id}",
                            json.dumps(session_info),
                            ex=int(self.session_timeout_minutes * 60)
                        )
                        
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Session validation error: {e}")
            return False
    
    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate user session"""
        try:
            # Remove from cache
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            # Remove from Redis
            if self.redis_client:
                self.redis_client.delete(f"auth:session:{session_id}")
            
            logger.info(f"Invalidated session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to invalidate session: {e}")
            return False
    
    def check_permission(self, token_or_key: str, permission: str) -> bool:
        """Check if token/key has specific permission"""
        try:
            # Try JWT token first
            try:
                payload = jwt.decode(token_or_key, self.jwt_secret, algorithms=[self.jwt_algorithm])
                permissions = payload.get("permissions", [])
                return permission in permissions or "admin" in permissions
            except jwt.InvalidTokenError:
                pass
            
            # Try API key
            if token_or_key in self.api_keys:
                key_info = self.api_keys[token_or_key]
                permissions = key_info.get("permissions", [])
                return permission in permissions or "admin" in permissions
            
            return False
            
        except Exception as e:
            logger.error(f"Permission check error: {e}")
            return False
    
    async def _load_api_keys(self):
        """Load API keys from Redis"""
        try:
            if self.redis_client:
                keys = self.redis_client.keys("auth:api_key:*")
                for key in keys:
                    data = self.redis_client.get(key)
                    if data:
                        api_key = key.decode().split(":")[-1]
                        key_info = json.loads(data)
                        self.api_keys[api_key] = key_info
                
                logger.info(f"Loaded {len(self.api_keys)} API keys")
                
        except Exception as e:
            logger.error(f"Failed to load API keys: {e}")

# Global auth manager instance
auth_manager = AuthManager()

def authenticate_token(token: str) -> bool:
    """Convenience function for token authentication"""
    return auth_manager.authenticate_token(token)

def generate_server_token(server_id: str, permissions: list = None) -> str:
    """Convenience function for generating server tokens"""
    return auth_manager.generate_server_token(server_id, permissions)
