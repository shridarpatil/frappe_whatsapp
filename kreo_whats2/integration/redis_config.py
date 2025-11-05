#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

"""
Configuración de Redis con Connection Pooling para kreo_whats2
Implementa connection pooling, timeouts y retry logic para alta concurrencia
"""

import redis
import logging
import time
from typing import Optional, Dict, Any
from redis.connection import ConnectionPool
from frappe import _

from kreo_whats2.kreo_whats2.utils.logging_manager import get_logger, log_event, log_performance, log_error, logging_manager

logger = get_logger("redis_config")

class RedisConnectionManager:
    """Gestor de conexiones Redis con pooling para alta concurrencia"""
    
    def __init__(self):
        self.pools: Dict[str, ConnectionPool] = {}
        self.clients: Dict[str, redis.Redis] = {}
        self._setup_default_pools()
    
    def _setup_default_pools(self):
        """Configurar pools Redis por defecto"""
        try:
            # Pool para cola de mensajes (100 conexiones concurrentes)
            self.pools['queue'] = ConnectionPool(
                host='redis-queue',
                port=6379,
                db=1,
                max_connections=100,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={
                    redis.connection.TCP_USER_TIMEOUT: 300,
                    redis.connection.TCP_NODELAY: True
                },
                health_check_interval=30,
                socket_connect_timeout=10,
                socket_timeout=30
            )
            
            # Pool para caché (50 conexiones)
            self.pools['cache'] = ConnectionPool(
                host='redis-cache',
                port=6379,
                db=0,
                max_connections=50,
                retry_on_timeout=True,
                socket_keepalive=True,
                health_check_interval=30,
                socket_connect_timeout=5,
                socket_timeout=15
            )
            
            # Pool para SocketIO (25 conexiones)
            self.pools['socketio'] = ConnectionPool(
                host='redis-socketio',
                port=6379,
                db=0,
                max_connections=25,
                retry_on_timeout=True,
                socket_keepalive=True,
                health_check_interval=30,
                socket_connect_timeout=5,
                socket_timeout=15
            )
            
            # Logging estructurado para configuración de pools
            log_event(
                "redis_config",
                "INFO",
                "Pools Redis configurados exitosamente",
                operation="redis_pool_setup",
                performance_metrics={
                    "pool_count": len(self.pools),
                    "total_max_connections": sum(pool.max_connections for pool in self.pools.values())
                },
                business_metrics={
                    "infrastructure_readiness": True,
                    "connection_capacity": sum(pool.max_connections for pool in self.pools.values())
                },
                metadata={
                    "component": "redis_configuration",
                    "pool_types": list(self.pools.keys())
                }
            )
            
        except Exception as e:
            log_error("redis_config", e, {
                "operation": "redis_pool_setup",
                "error_type": "pool_configuration_failure"
            })
            logger.error(f"Error configurando pools Redis: {str(e)}")
            raise
    
    def get_client(self, pool_name: str = 'queue') -> Optional[redis.Redis]:
        """Obtener cliente Redis con connection pooling"""
        if pool_name not in self.clients:
            try:
                if pool_name not in self.pools:
                    logger.warning(f"Pool {pool_name} no configurado, usando pool por defecto")
                    pool_name = 'queue'
                
                # Crear cliente con retry logic
                client = redis.Redis(
                    connection_pool=self.pools[pool_name],
                    retry=redis.Retry(
                        redis.Backoff.exponential(backoff=1, maximum=60),
                        retries=3
                    ),
                    health_check_interval=30
                )
                
                # Probar conexión
                client.ping()
                self.clients[pool_name] = client
                logger.info(f"Cliente Redis {pool_name} creado exitosamente")
                
            except Exception as e:
                logger.error(f"Error creando cliente Redis {pool_name}: {str(e)}")
                return None
        
        return self.clients[pool_name]
    
    def get_queue_client(self) -> redis.Redis:
        """Obtener cliente para cola de mensajes"""
        client = self.get_client('queue')
        if not client:
            raise ConnectionError("No se puede conectar al cliente Redis Queue")
        return client
    
    def get_cache_client(self) -> redis.Redis:
        """Obtener cliente para caché"""
        client = self.get_client('cache')
        if not client:
            raise ConnectionError("No se puede conectar al cliente Redis Cache")
        return client
    
    def get_socketio_client(self) -> redis.Redis:
        """Obtener cliente para SocketIO"""
        client = self.get_client('socketio')
        if not client:
            raise ConnectionError("No se puede conectar al cliente Redis SocketIO")
        return client
    
    def test_connection(self, pool_name: str = 'queue') -> bool:
        """Testear conexión a Redis"""
        try:
            client = self.get_client(pool_name)
            if client:
                client.ping()
                return True
        except Exception as e:
            logger.error(f"Error testando conexión Redis {pool_name}: {str(e)}")
            return False
        return False
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de los pools"""
        stats = {}
        
        for pool_name, pool in self.pools.items():
            try:
                # Estadísticas del pool
                stats[pool_name] = {
                    'max_connections': pool.max_connections,
                    'available_connections': len(pool._available_connections),
                    'in_use_connections': len(pool._in_use_connections),
                    'total_connections': len(pool._created_connections),
                    'connection_ratio': len(pool._in_use_connections) / pool.max_connections
                }
            except Exception as e:
                logger.error(f"Error obteniendo estadísticas del pool {pool_name}: {str(e)}")
                stats[pool_name] = {'error': str(e)}
        
        return stats
    
    def close_all_connections(self):
        """Cerrar todas las conexiones"""
        for client in self.clients.values():
            try:
                client.close()
            except Exception as e:
                logger.error(f"Error cerrando cliente Redis: {str(e)}")
        
        self.clients.clear()
        logger.info("Todas las conexiones Redis cerradas")

# Instancia global del gestor de conexiones
redis_manager = RedisConnectionManager()

def get_redis_client(pool_name: str = 'queue') -> redis.Redis:
    """Función de conveniencia para obtener cliente Redis"""
    return redis_manager.get_client(pool_name)

def get_queue_client() -> redis.Redis:
    """Función de conveniencia para obtener cliente de cola"""
    return redis_manager.get_queue_client()

def get_cache_client() -> redis.Redis:
    """Función de conveniencia para obtener cliente de caché"""
    return redis_manager.get_cache_client()

def get_socketio_client() -> redis.Redis:
    """Función de conveniencia para obtener cliente de SocketIO"""
    return redis_manager.get_socketio_client()

def test_redis_connection(pool_name: str = 'queue') -> bool:
    """Función de conveniencia para testear conexión Redis"""
    return redis_manager.test_connection(pool_name)

def get_redis_stats() -> Dict[str, Any]:
    """Función de conveniencia para obtener estadísticas Redis"""
    return redis_manager.get_pool_stats()