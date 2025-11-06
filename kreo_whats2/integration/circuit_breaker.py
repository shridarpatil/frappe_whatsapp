#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

"""
Circuit Breaker para servicios de WhatsApp
Implementa patrones de resiliencia con estados OPEN/CLOSED/HALF-OPEN
"""

import time
import logging
import json
import functools
from enum import Enum
from typing import Optional, Dict, Any, Callable, Union
from dataclasses import dataclass, field
from frappe import _

from kreo_whats2.kreo_whats2.integration.redis_config import redis_manager
from kreo_whats2.kreo_whats2.utils.logging_manager import get_logger, log_event, log_performance, log_error, logging_manager

logger = get_logger("circuit_breaker")

# Decoradores para circuit breaker
def log_circuit_breaker_event(level: str = "INFO", operation: str = None):
    """Decorador para logging de eventos de circuit breaker"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            circuit_name = args[0].config.name if args and hasattr(args[0], 'config') else "unknown"
            
            try:
                result = func(*args, **kwargs)
                
                # Logging de éxito
                log_event(
                    "circuit_breaker",
                    level,
                    f"Operación exitosa: {func.__name__} en circuito {circuit_name}",
                    operation=operation or func.__name__,
                    performance_metrics={
                        "execution_time": time.time() - start_time,
                        "circuit_name": circuit_name,
                        "operation": func.__name__
                    },
                    business_metrics={
                        "circuit_health": True,
                        "operation_success": True
                    },
                    metadata={
                        "component": "circuit_breaker",
                        "circuit_name": circuit_name,
                        "function": func.__name__
                    }
                )
                
                return result
                
            except Exception as e:
                # Logging de error
                log_error("circuit_breaker", e, {
                    "operation": operation or func.__name__,
                    "circuit_name": circuit_name,
                    "function": func.__name__
                })
                raise
                
        return wrapper
    return decorator

def handle_circuit_breaker_errors(operation: str = None):
    """Decorador para manejo de errores en circuit breaker"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            circuit_name = args[0].config.name if args and hasattr(args[0], 'config') else "unknown"
            
            try:
                result = func(*args, **kwargs)
                
                # Registrar métricas de performance
                execution_time = time.time() - start_time
                log_performance(
                    "circuit_breaker",
                    execution_time,
                    {
                        "circuit_name": circuit_name,
                        "operation": operation or func.__name__,
                        "success": True
                    }
                )
                
                return result
                
            except Exception as e:
                # Registrar error con contexto completo
                log_error("circuit_breaker", e, {
                    "operation": operation or func.__name__,
                    "circuit_name": circuit_name,
                    "execution_time": time.time() - start_time,
                    "error_type": type(e).__name__
                })
                raise
                
        return wrapper
    return decorator

class CircuitState(Enum):
    """Estados del circuit breaker"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit broken, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service is back

@dataclass
class CircuitBreakerConfig:
    """Configuración del circuit breaker"""
    failure_threshold: int = 5      # Número de fallos antes de abrir
    recovery_timeout: int = 60      # Segundos antes de pasar a HALF_OPEN
    expected_exception: type = Exception  # Excepción que consideramos fallo
    fallback_function: Optional[Callable] = None  # Función de fallback
    name: str = "default"           # Nombre del circuit breaker
    redis_key_prefix: str = "circuit_breaker"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'failure_threshold': self.failure_threshold,
            'recovery_timeout': self.recovery_timeout,
            'expected_exception': self.expected_exception.__name__,
            'name': self.name,
            'redis_key_prefix': self.redis_key_prefix
        }

@dataclass
class CircuitBreakerState:
    """Estado actual del circuit breaker"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0
    success_count: int = 0
    last_success_time: float = 0
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'state': self.state.value,
            'failure_count': self.failure_count,
            'last_failure_time': self.last_failure_time,
            'success_count': self.success_count,
            'last_success_time': self.last_success_time,
            'total_requests': self.total_requests,
            'total_failures': self.total_failures,
            'total_successes': self.total_successes
        }

class CircuitBreaker:
    """Implementación del patrón Circuit Breaker"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState()
        self.redis_client = redis_manager.get_cache_client()
        self._setup_redis_keys()
    
    def _setup_redis_keys(self):
        """Configurar claves Redis para persistencia del estado"""
        self.state_key = f"{self.config.redis_key_prefix}:{self.config.name}:state"
        self.metrics_key = f"{self.config.redis_key_prefix}:{self.config.name}:metrics"
    
    def _load_state_from_redis(self):
        """Cargar estado desde Redis"""
        try:
            if not self.redis_client:
                return
            
            state_data = self.redis_client.get(self.state_key)
            if state_data:
                state_dict = json.loads(state_data)
                self.state = CircuitBreakerState(**state_dict)
                self.state.state = CircuitState(self.state.state)
                
        except Exception as e:
            logger.warning(f"Error cargando estado desde Redis: {str(e)}")
    
    def _save_state_to_redis(self):
        """Guardar estado en Redis"""
        try:
            if not self.redis_client:
                return
            
            state_data = json.dumps(self.state.to_dict())
            self.redis_client.setex(self.state_key, 3600, state_data)  # 1 hora de expiración
            
        except Exception as e:
            logger.warning(f"Error guardando estado en Redis: {str(e)}")
    
    def _should_open_circuit(self) -> bool:
        """Determinar si se debe abrir el circuito"""
        now = time.time()
        time_since_last_failure = now - self.state.last_failure_time
        
        # Si hay suficientes fallos y no ha pasado el tiempo de recuperación
        return (
            self.state.failure_count >= self.config.failure_threshold and
            time_since_last_failure < self.config.recovery_timeout
        )
    
    def _should_close_circuit(self) -> bool:
        """Determinar si se debe cerrar el circuito"""
        now = time.time()
        time_since_last_failure = now - self.state.last_failure_time
        
        # Si ha pasado el tiempo de recuperación
        return time_since_last_failure >= self.config.recovery_timeout
    
    def _record_success(self):
        """Registrar éxito"""
        self.state.success_count += 1
        self.state.last_success_time = time.time()
        self.state.total_requests += 1
        self.state.total_successes += 1
        
        # Si estamos en HALF_OPEN y tenemos éxito, cerrar el circuito
        if self.state.state == CircuitState.HALF_OPEN:
            self.state.state = CircuitState.CLOSED
            self.state.failure_count = 0
            self.state.success_count = 0
        
        self._save_state_to_redis()
        logger.debug(f"Circuit breaker {self.config.name}: éxito registrado")
    
    def _record_failure(self):
        """Registrar fallo"""
        self.state.failure_count += 1
        self.state.last_failure_time = time.time()
        self.state.total_requests += 1
        self.state.total_failures += 1
        
        # Si alcanzamos el umbral de fallos, abrir el circuito
        if self.state.failure_count >= self.config.failure_threshold:
            self.state.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker {self.config.name}: circuito abierto por {self.state.failure_count} fallos")
        
        self._save_state_to_redis()
    
    def _check_state(self):
        """Verificar y actualizar estado del circuito"""
        # Cargar estado desde Redis si es necesario
        if self.state.total_requests == 0:
            self._load_state_from_redis()
        
        # Si estamos en OPEN, verificar si podemos pasar a HALF_OPEN
        if self.state.state == CircuitState.OPEN and self._should_close_circuit():
            self.state.state = CircuitState.HALF_OPEN
            self.state.success_count = 0
            logger.info(f"Circuit breaker {self.config.name}: pasando a HALF_OPEN")
        
        self._save_state_to_redis()
    
    @log_circuit_breaker_event("INFO", "circuit_breaker_call")
    @handle_circuit_breaker_errors("circuit_breaker_call")
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Ejecutar función con circuit breaker"""
        self._check_state()
        
        # Verificar estado actual
        if self.state.state == CircuitState.OPEN:
            logger.warning(f"Circuit breaker {self.config.name}: circuito abierto, llamada rechazada")
            
            # Intentar fallback si está disponible
            if self.config.fallback_function:
                try:
                    logger.info(f"Ejecutando función de fallback para {self.config.name}")
                    return self.config.fallback_function(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error en función de fallback: {str(e)}")
                    raise Exception(f"Circuit breaker abierto y fallback fallido: {str(e)}")
            else:
                raise Exception(f"Circuit breaker {self.config.name} está abierto")
        
        # Ejecutar la función
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
            
        except self.config.expected_exception as e:
            self._record_failure()
            raise
            
        except Exception as e:
            # Para excepciones no esperadas, registrar como fallo pero no incrementar contador
            logger.warning(f"Excepción inesperada en {self.config.name}: {str(e)}")
            self.state.total_requests += 1
            raise
    
    def get_state(self) -> Dict[str, Any]:
        """Obtener estado actual"""
        self._check_state()
        return {
            'name': self.config.name,
            'state': self.state.state.value,
            'failure_count': self.state.failure_count,
            'success_count': self.state.success_count,
            'total_requests': self.state.total_requests,
            'total_failures': self.state.total_failures,
            'total_successes': self.state.total_successes,
            'failure_rate': self.state.total_failures / self.state.total_requests if self.state.total_requests > 0 else 0,
            'last_failure_time': self.state.last_failure_time,
            'last_success_time': self.state.last_success_time
        }
    
    def reset(self):
        """Resetear circuit breaker"""
        self.state = CircuitBreakerState()
        self._save_state_to_redis()
        logger.info(f"Circuit breaker {self.config.name} reseteado")
    
    def force_open(self):
        """Forzar estado OPEN"""
        self.state.state = CircuitState.OPEN
        self._save_state_to_redis()
        logger.warning(f"Circuit breaker {self.config.name} forzado a OPEN")
    
    def force_close(self):
        """Forzar estado CLOSED"""
        self.state.state = CircuitState.CLOSED
        self.state.failure_count = 0
        self._save_state_to_redis()
        logger.info(f"Circuit breaker {self.config.name} forzado a CLOSED")

class WhatsAppCircuitBreaker:
    """Gestor de circuit breakers para servicios de WhatsApp"""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
        self._setup_default_breakers()
    
    def _setup_default_breakers(self):
        """Configurar circuit breakers por defecto"""
        # Circuit breaker para Meta API
        meta_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30,
            name="meta-api",
            fallback_function=self._meta_api_fallback
        )
        self.breakers['meta-api'] = CircuitBreaker(meta_config)
        
        # Circuit breaker para Redis
        redis_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=15,
            name="redis-queue",
            fallback_function=self._redis_fallback
        )
        self.breakers['redis-queue'] = CircuitBreaker(redis_config)
        
        # Circuit breaker para base de datos
        db_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=20,
            name="database",
            fallback_function=self._database_fallback
        )
        self.breakers['database'] = CircuitBreaker(db_config)
        
        logger.info("Circuit breakers por defecto configurados")
    
    def _meta_api_fallback(self, *args, **kwargs):
        """Función de fallback para Meta API"""
        logger.warning("Usando fallback para Meta API")
        return {
            'success': False,
            'error': 'Meta API no disponible (fallback)',
            'retryable': True,
            'fallback': True
        }
    
    def _redis_fallback(self, *args, **kwargs):
        """Función de fallback para Redis"""
        logger.warning("Usando fallback para Redis")
        return {
            'success': False,
            'error': 'Redis no disponible (fallback)',
            'retryable': True,
            'fallback': True
        }
    
    def _database_fallback(self, *args, **kwargs):
        """Función de fallback para base de datos"""
        logger.warning("Usando fallback para base de datos")
        return {
            'success': False,
            'error': 'Base de datos no disponible (fallback)',
            'retryable': True,
            'fallback': True
        }
    
    def get_breaker(self, name: str) -> CircuitBreaker:
        """Obtener circuit breaker por nombre"""
        if name not in self.breakers:
            # Crear circuit breaker dinámico
            config = CircuitBreakerConfig(name=name)
            self.breakers[name] = CircuitBreaker(config)
            logger.info(f"Circuit breaker dinámico creado: {name}")
        
        return self.breakers[name]
    
    def call_with_circuit(self, name: str, func: Callable, *args, **kwargs) -> Any:
        """Llamar función con circuit breaker"""
        breaker = self.get_breaker(name)
        return breaker.call(func, *args, **kwargs)
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Obtener estados de todos los circuit breakers"""
        states = {}
        for name, breaker in self.breakers.items():
            states[name] = breaker.get_state()
        return states
    
    def reset_all(self):
        """Resetear todos los circuit breakers"""
        for breaker in self.breakers.values():
            breaker.reset()
        logger.info("Todos los circuit breakers reseteados")

# Decorador para usar circuit breaker fácilmente
def circuit_breaker(name: str, fallback: Optional[Callable] = None):
    """Decorador para aplicar circuit breaker a funciones"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Obtener o crear circuit breaker
            whatsapp_cb = WhatsAppCircuitBreaker()
            breaker = whatsapp_cb.get_breaker(name)
            
            # Configurar fallback si se proporciona
            if fallback:
                breaker.config.fallback_function = fallback
            
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator

# Instancia global del gestor de circuit breakers
circuit_breaker_manager = WhatsAppCircuitBreaker()

def call_with_circuit(name: str, func: Callable, *args, **kwargs) -> Any:
    """Función de conveniencia para llamar con circuit breaker"""
    return circuit_breaker_manager.call_with_circuit(name, func, *args, **kwargs)

def get_circuit_state(name: str) -> Dict[str, Any]:
    """Función de conveniencia para obtener estado"""
    return circuit_breaker_manager.get_breaker(name).get_state()

def get_all_circuit_states() -> Dict[str, Dict[str, Any]]:
    """Función de conveniencia para obtener todos los estados"""
    return circuit_breaker_manager.get_all_states()

def reset_circuit(name: str):
    """Función de conveniencia para resetear circuit breaker"""
    circuit_breaker_manager.get_breaker(name).reset()

def force_circuit_open(name: str):
    """Función de conveniencia para forzar estado OPEN"""
    circuit_breaker_manager.get_breaker(name).force_open()

def force_circuit_close(name: str):
    """Función de conveniencia para forzar estado CLOSED"""
    circuit_breaker_manager.get_breaker(name).force_close()