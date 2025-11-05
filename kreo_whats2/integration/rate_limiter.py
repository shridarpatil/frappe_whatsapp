#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

"""
Rate Limiter con algoritmo Token Bucket para WhatsApp
Implementa control de tasa de 10 mensajes por segundo con Redis
"""

import redis
import time
import logging
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass
from frappe import _

from kreo_whats2.kreo_whats2.integration.redis_config import redis_manager
from kreo_whats2.kreo_whats2.utils.logging_manager import get_logger, log_event, log_performance, log_error, logging_manager

logger = get_logger("rate_limiter")

@dataclass
class RateLimitConfig:
    """Configuración de rate limiting"""
    rate_limit: int = 10  # Mensajes por segundo
    burst_limit: int = 20  # Límite de ráfaga
    window_size: int = 1   # Tamaño de ventana en segundos
    redis_key_prefix: str = "rate_limit"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'rate_limit': self.rate_limit,
            'burst_limit': self.burst_limit,
            'window_size': self.window_size,
            'redis_key_prefix': self.redis_key_prefix
        }

class TokenBucket:
    """Implementación del algoritmo Token Bucket"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.redis_client = redis_manager.get_cache_client()
        self._setup_scripts()
    
    def _setup_scripts(self):
        """Configurar scripts Lua para Redis"""
        # Script para consumir tokens de forma atómica
        self.consume_script = """
        local key = KEYS[1]
        local rate_limit = tonumber(ARGV[1])
        local burst_limit = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local tokens_to_consume = tonumber(ARGV[4] or 1)
        
        -- Obtener estado actual del bucket
        local bucket_data = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket_data[1]) or burst_limit
        local last_refill = tonumber(bucket_data[2]) or now
        
        -- Calcular tokens acumulados desde el último refill
        local time_passed = now - last_refill
        local tokens_added = math.floor(time_passed * rate_limit)
        tokens = math.min(burst_limit, tokens + tokens_added)
        
        -- Verificar si hay suficientes tokens
        if tokens >= tokens_to_consume then
            tokens = tokens - tokens_to_consume
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 60)  -- Expirar después de 60 segundos
            return {1, tokens, burst_limit - tokens}
        else
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 60)
            return {0, tokens, burst_limit - tokens}
        end
        """
        
        # Script para obtener estado del bucket
        self.get_state_script = """
        local key = KEYS[1]
        local rate_limit = tonumber(ARGV[1])
        local burst_limit = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        
        local bucket_data = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket_data[1]) or burst_limit
        local last_refill = tonumber(bucket_data[2]) or now
        
        local time_passed = now - last_refill
        local tokens_added = math.floor(time_passed * rate_limit)
        tokens = math.min(burst_limit, tokens + tokens_added)
        
        return {tokens, burst_limit, tokens_added, time_passed}
        """
    
    def _get_bucket_key(self, identifier: str) -> str:
        """Obtener clave Redis para el bucket"""
        return f"{self.config.redis_key_prefix}:{identifier}"
    
    def consume(self, identifier: str, tokens: int = 1) -> Dict[str, Any]:
        """Consumir tokens del bucket"""
        if not self.redis_client:
            logger.warning("Redis client not available, bypassing rate limit")
            return {
                'allowed': True,
                'tokens_remaining': self.config.burst_limit - tokens,
                'retry_after': 0
            }
        
        try:
            bucket_key = self._get_bucket_key(identifier)
            now = int(time.time())
            
            # Ejecutar script Lua de forma atómica
            result = self.redis_client.eval(
                self.consume_script,
                1,
                bucket_key,
                self.config.rate_limit,
                self.config.burst_limit,
                now,
                tokens
            )
            
            allowed = bool(result[0])
            tokens_remaining = int(result[1])
            tokens_consumed = int(result[2])
            
            if allowed:
                logger.debug(f"Tokens consumidos para {identifier}: {tokens}, restantes: {tokens_remaining}")
                return {
                    'allowed': True,
                    'tokens_remaining': tokens_remaining,
                    'retry_after': 0
                }
            else:
                # Calcular tiempo de espera para el próximo token
                wait_time = max(1, (tokens - tokens_remaining) // self.config.rate_limit)
                logger.warning(f"Límite de tasa alcanzado para {identifier}. Tokens: {tokens_remaining}/{self.config.burst_limit}")
                return {
                    'allowed': False,
                    'tokens_remaining': tokens_remaining,
                    'retry_after': wait_time
                }
                
        except Exception as e:
            logger.error(f"Error en rate limiting para {identifier}: {str(e)}")
            # En caso de error, permitir la operación para no bloquear el sistema
            return {
                'allowed': True,
                'tokens_remaining': self.config.burst_limit - tokens,
                'retry_after': 0
            }
    
    def get_state(self, identifier: str) -> Dict[str, Any]:
        """Obtener estado actual del bucket"""
        if not self.redis_client:
            return {
                'tokens': self.config.burst_limit,
                'burst_limit': self.config.burst_limit,
                'tokens_added': 0,
                'time_passed': 0
            }
        
        try:
            bucket_key = self._get_bucket_key(identifier)
            now = int(time.time())
            
            result = self.redis_client.eval(
                self.get_state_script,
                1,
                bucket_key,
                self.config.rate_limit,
                self.config.burst_limit,
                now
            )
            
            return {
                'tokens': int(result[0]),
                'burst_limit': int(result[1]),
                'tokens_added': int(result[2]),
                'time_passed': int(result[3])
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estado del bucket para {identifier}: {str(e)}")
            return {
                'tokens': self.config.burst_limit,
                'burst_limit': self.config.burst_limit,
                'tokens_added': 0,
                'time_passed': 0
            }
    
    def reset(self, identifier: str) -> bool:
        """Resetear bucket para un identificador"""
        if not self.redis_client:
            return False
        
        try:
            bucket_key = self._get_bucket_key(identifier)
            self.redis_client.delete(bucket_key)
            logger.info(f"Bucket reseteado para {identifier}")
            return True
            
        except Exception as e:
            logger.error(f"Error reseteando bucket para {identifier}: {str(e)}")
            return False
    
    def get_usage_stats(self, identifier: str) -> Dict[str, Any]:
        """Obtener estadísticas de uso"""
        state = self.get_state(identifier)
        return {
            'identifier': identifier,
            'current_tokens': state['tokens'],
            'burst_limit': state['burst_limit'],
            'tokens_used': state['burst_limit'] - state['tokens'],
            'usage_percentage': (state['burst_limit'] - state['tokens']) / state['burst_limit'] * 100,
            'tokens_added_this_second': state['tokens_added'],
            'last_activity': int(time.time())
        }

class WhatsAppRateLimiter:
    """Gestor de rate limiting para WhatsApp"""
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self.bucket = TokenBucket(self.config)
        self._setup_default_limits()
    
    def _setup_default_limits(self):
        """Configurar límites por defecto con logging estructurado"""
        # Límites por tipo de operación
        self.operation_limits = {
            'send_message': 1,      # 1 token por mensaje
            'send_template': 1,     # 1 token por plantilla
            'send_bulk': 5,         # 5 tokens por envío masivo
            'api_call': 1,          # 1 token por llamada API
            'webhook_processing': 2 # 2 tokens por procesamiento webhook
        }
        
        # Logging estructurado para inicialización de rate limiter
        log_event(
            "rate_limiter",
            "INFO",
            f"Rate limiter inicializado: {self.config.rate_limit} msg/s, burst: {self.config.burst_limit}",
            operation="rate_limiter_setup",
            performance_metrics={
                "rate_limit": self.config.rate_limit,
                "burst_limit": self.config.burst_limit,
                "operation_types": len(self.operation_limits),
                "operation_limits": self.operation_limits
            },
            business_metrics={
                "throttling_enabled": True,
                "max_concurrent_requests": self.config.burst_limit
            },
            metadata={
                "component": "rate_limiter_configuration",
                "window_size": self.config.window_size
            }
        )
    
    def check_rate_limit(self, identifier: str, operation: str = 'send_message') -> Dict[str, Any]:
        """Verificar y consumir límite de tasa"""
        tokens = self.operation_limits.get(operation, 1)
        
        result = self.bucket.consume(identifier, tokens)
        
        # Registrar métricas
        self._log_rate_limit_event(identifier, operation, result)
        
        return result
    
    def is_allowed(self, identifier: str, operation: str = 'send_message') -> bool:
        """Verificar si una operación está permitida"""
        result = self.check_rate_limit(identifier, operation)
        return result['allowed']
    
    def get_remaining_tokens(self, identifier: str) -> int:
        """Obtener tokens restantes"""
        state = self.bucket.get_state(identifier)
        return state['tokens']
    
    def wait_if_needed(self, identifier: str, operation: str = 'send_message') -> float:
        """Esperar si es necesario para respetar el límite"""
        result = self.check_rate_limit(identifier, operation)
        
        if not result['allowed']:
            wait_time = result['retry_after']
            if wait_time > 0:
                logger.info(f"Esperando {wait_time} segundos para {identifier}")
                time.sleep(wait_time)
                return wait_time
        
        return 0
    
    def _log_rate_limit_event(self, identifier: str, operation: str, result: Dict[str, Any]):
        """Registrar evento de rate limiting"""
        event_data = {
            'identifier': identifier,
            'operation': operation,
            'allowed': result['allowed'],
            'tokens_remaining': result['tokens_remaining'],
            'retry_after': result['retry_after'],
            'timestamp': time.time()
        }
        
        if result['allowed']:
            logger.debug(f"Rate limit permitido: {json.dumps(event_data)}")
        else:
            logger.warning(f"Rate limit bloqueado: {json.dumps(event_data)}")
    
    def get_global_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas globales de rate limiting"""
        try:
            # Obtener todas las claves de rate limiting
            pattern = f"{self.config.redis_key_prefix}:*"
            keys = self.redis_client.keys(pattern) if self.redis_client else []
            
            total_buckets = len(keys)
            active_buckets = 0
            total_tokens = 0
            total_burst_limit = 0
            
            for key in keys[:10]:  # Limitar a 10 para performance
                try:
                    identifier = key.decode().split(':', 2)[2]
                    state = self.get_remaining_tokens(identifier)
                    if state < self.config.burst_limit:
                        active_buckets += 1
                        total_tokens += state
                        total_burst_limit += self.config.burst_limit
                except:
                    continue
            
            return {
                'total_buckets': total_buckets,
                'active_buckets': active_buckets,
                'global_usage_percentage': (total_burst_limit - total_tokens) / total_burst_limit * 100 if total_burst_limit > 0 else 0,
                'current_limit': self.config.rate_limit,
                'current_burst': self.config.burst_limit
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas globales: {str(e)}")
            return {
                'total_buckets': 0,
                'active_buckets': 0,
                'global_usage_percentage': 0,
                'current_limit': self.config.rate_limit,
                'current_burst': self.config.burst_limit
            }

# Instancia global del rate limiter
rate_limiter = WhatsAppRateLimiter()

def check_rate_limit(identifier: str, operation: str = 'send_message') -> Dict[str, Any]:
    """Función de conveniencia para verificar límite de tasa"""
    return rate_limiter.check_rate_limit(identifier, operation)

def is_rate_limit_allowed(identifier: str, operation: str = 'send_message') -> bool:
    """Función de conveniencia para verificar si está permitido"""
    return rate_limiter.is_allowed(identifier, operation)

def wait_for_rate_limit(identifier: str, operation: str = 'send_message') -> float:
    """Función de conveniencia para esperar si es necesario"""
    return rate_limiter.wait_if_needed(identifier, operation)

def get_rate_limit_stats(identifier: str) -> Dict[str, Any]:
    """Función de conveniencia para obtener estadísticas"""
    return rate_limiter.bucket.get_usage_stats(identifier)