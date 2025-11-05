#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

"""
Configuración de Auto-Scaling para WhatsApp
Implementa escalado automático basado en métricas de cola, CPU, memoria y errores
"""

import time
import logging
import json
import subprocess
import threading
import docker
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from frappe import _

from kreo_whats2.kreo_whats2.integration.monitoring import metrics_collector
from kreo_whats2.kreo_whats2.integration.health_checker import health_checker
from kreo_whats2.kreo_whats2.utils.logging_manager import get_logger, log_event, log_performance, log_error, logging_manager

logger = get_logger("auto_scaling")

# Decoradores para auto-scaling
def log_auto_scaling_event(level: str = "INFO", operation: str = None):
    """Decorador para logging de eventos de auto-scaling"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Logging de éxito
                log_event(
                    "auto_scaling",
                    level,
                    f"Operación exitosa: {func.__name__}",
                    operation=operation or func.__name__,
                    performance_metrics={
                        "execution_time": time.time() - start_time,
                        "function": func.__name__
                    },
                    business_metrics={
                        "scaling_operation": True,
                        "operation_success": True
                    },
                    metadata={
                        "component": "auto_scaling",
                        "function": func.__name__
                    }
                )
                
                return result
                
            except Exception as e:
                # Logging de error
                log_error("auto_scaling", e, {
                    "operation": operation or func.__name__,
                    "function": func.__name__
                })
                raise
                
        return wrapper
    return decorator

def handle_auto_scaling_errors(operation: str = None):
    """Decorador para manejo de errores en auto-scaling"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Registrar métricas de performance
                execution_time = time.time() - start_time
                log_performance(
                    "auto_scaling",
                    execution_time,
                    {
                        "operation": operation or func.__name__,
                        "success": True
                    }
                )
                
                return result
                
            except Exception as e:
                # Registrar error con contexto completo
                log_error("auto_scaling", e, {
                    "operation": operation or func.__name__,
                    "execution_time": time.time() - start_time,
                    "error_type": type(e).__name__
                })
                raise
                
        return wrapper
    return decorator

class ScalingAction(Enum):
    """Acciones de escalado"""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_ACTION = "no_action"
    EMERGENCY_SCALE_UP = "emergency_scale_up"

@dataclass
class ScalingRule:
    """Regla de escalado"""
    name: str
    metric: str
    condition: str  # ">", "<", ">=", "<=", "=="
    threshold: float
    duration: int  # segundos
    action: ScalingAction
    weight: float = 1.0  # Peso de la regla (0.0 - 1.0)
    cooldown: int = 300  # tiempo de cooldown en segundos

@dataclass
class ScalingDecision:
    """Decisión de escalado"""
    action: ScalingAction
    reason: str
    confidence: float  # 0.0 - 1.0
    timestamp: float
    current_metrics: Dict[str, float] = field(default_factory=dict)
    recommended_instances: int = 1

class AutoScalingManager:
    """Gestor de auto-scaling para WhatsApp"""
    
    def __init__(self):
        self.docker_client = None
        self.scaling_rules: List[ScalingRule] = []
        self.last_scaling_action = None
        self.scaling_history: List[ScalingDecision] = []
        self.current_instances = 1
        self.max_instances = 5
        self.min_instances = 1
        self._setup_default_rules()
        self._setup_docker_client()
        self._start_scaling_monitor()
    
    def _setup_docker_client(self):
        """Configurar cliente Docker"""
        try:
            self.docker_client = docker.from_env()
            logger.info("Cliente Docker configurado exitosamente")
        except Exception as e:
            logger.error(f"No se puede conectar a Docker: {str(e)}")
            self.docker_client = None
    
    def _setup_default_rules(self):
        """Configurar reglas de escalado por defecto"""
        self.scaling_rules = [
            # Escalar hacia arriba por cola larga
            ScalingRule(
                name="queue_size_scale_up",
                metric="whatsapp_queue_size",
                condition=">",
                threshold=500,
                duration=60,
                action=ScalingAction.SCALE_UP,
                weight=0.9,
                cooldown=300
            ),
            
            # Escalar hacia arriba por alta tasa de errores
            ScalingRule(
                name="error_rate_scale_up",
                metric="whatsapp_messages_error_rate",
                condition=">",
                threshold=0.15,  # 15% de errores
                duration=120,
                action=ScalingAction.SCALE_UP,
                weight=0.8,
                cooldown=600
            ),
            
            # Escalar hacia arriba por circuit breaker abierto
            ScalingRule(
                name="circuit_breaker_scale_up",
                metric="whatsapp_circuit_breaker_state",
                condition="==",
                threshold=1.0,  # 1 = OPEN
                duration=30,
                action=ScalingAction.EMERGENCY_SCALE_UP,
                weight=1.0,
                cooldown=180
            ),
            
            # Escalar hacia abajo por cola vacía y bajo uso
            ScalingRule(
                name="low_queue_scale_down",
                metric="whatsapp_queue_size",
                condition="<",
                threshold=50,
                duration=300,
                action=ScalingAction.SCALE_DOWN,
                weight=0.6,
                cooldown=600
            ),
            
            # Escalar hacia abajo por bajo uso de CPU
            ScalingRule(
                name="low_cpu_scale_down",
                metric="container_cpu_usage",
                condition="<",
                threshold=0.3,  # 30% de CPU
                duration=600,
                action=ScalingAction.SCALE_DOWN,
                weight=0.5,
                cooldown=900
            )
        ]
        
        logger.info(f"Reglas de escalado configuradas: {len(self.scaling_rules)}")
    
    def _start_scaling_monitor(self):
        """Iniciar monitor de escalado"""
        def monitor_scaling():
            while True:
                try:
                    self._evaluate_scaling_decision()
                    time.sleep(60)  # Evaluar cada 60 segundos
                except Exception as e:
                    logger.error(f"Error en monitor de escalado: {str(e)}")
                    time.sleep(120)  # Esperar más tiempo en caso de error
        
        thread = threading.Thread(target=monitor_scaling, daemon=True)
        thread.start()
        logger.info("Monitor de escalado iniciado")
    
    def _evaluate_scaling_decision(self):
        """Evaluar necesidad de escalado"""
        current_time = time.time()
        
        # Verificar cooldown
        if self.last_scaling_action:
            time_since_last = current_time - self.last_scaling_action
            if time_since_last < 60:  # Mínimo 60 segundos entre acciones
                return
        
        # Obtener métricas actuales
        current_metrics = self._get_current_metrics()
        
        # Evaluar reglas
        scale_up_score = 0.0
        scale_down_score = 0.0
        reasons = []
        
        for rule in self.scaling_rules:
            if self._evaluate_rule(rule, current_metrics):
                if rule.action == ScalingAction.SCALE_UP or rule.action == ScalingAction.EMERGENCY_SCALE_UP:
                    scale_up_score += rule.weight
                    reasons.append(f"{rule.name} (score: {rule.weight})")
                elif rule.action == ScalingAction.SCALE_DOWN:
                    scale_down_score += rule.weight
                    reasons.append(f"{rule.name} (score: {rule.weight})")
        
        # Tomar decisión
        decision = self._make_scaling_decision(scale_up_score, scale_down_score, reasons, current_metrics)
        
        if decision.action != ScalingAction.NO_ACTION:
            self._execute_scaling_action(decision)
    
    def _evaluate_rule(self, rule: ScalingRule, current_metrics: Dict[str, float]) -> bool:
        """Evaluar si una regla se cumple"""
        if rule.metric not in current_metrics:
            return False
        
        current_value = current_metrics[rule.metric]
        
        # Evaluar condición
        condition_met = False
        if rule.condition == ">" and current_value > rule.threshold:
            condition_met = True
        elif rule.condition == "<" and current_value < rule.threshold:
            condition_met = True
        elif rule.condition == ">=" and current_value >= rule.threshold:
            condition_met = True
        elif rule.condition == "<=" and current_value <= rule.threshold:
            condition_met = True
        elif rule.condition == "==" and abs(current_value - rule.threshold) < 0.01:
            condition_met = True
        
        if not condition_met:
            return False
        
        # Verificar duración (simplificado - en producción se verificaría historial)
        return True
    
    def _get_current_metrics(self) -> Dict[str, float]:
        """Obtener métricas actuales"""
        metrics = {}
        
        try:
            # Métricas de Prometheus
            prometheus_metrics = metrics_collector.get_dashboard_data()
            
            # Extraer métricas relevantes
            metrics['whatsapp_queue_size'] = prometheus_metrics.get('queue_metrics', {}).get('queue_size', 0)
            
            # Tasa de errores
            error_rate = prometheus_metrics.get('health_status', {}).get('error_rate', 0)
            metrics['whatsapp_messages_error_rate'] = error_rate
            
            # Estado de circuit breakers
            circuit_states = prometheus_metrics.get('circuit_breaker_states', {})
            for name, state in circuit_states.items():
                if state.get('state') == 'open':
                    metrics['whatsapp_circuit_breaker_state'] = 1.0
                    break
            else:
                metrics['whatsapp_circuit_breaker_state'] = 0.0
            
            # Métricas de contenedor
            container_metrics = self._get_container_metrics()
            metrics.update(container_metrics)
            
        except Exception as e:
            logger.error(f"Error obteniendo métricas actuales: {str(e)}")
        
        return metrics
    
    def _get_container_metrics(self) -> Dict[str, float]:
        """Obtener métricas de contenedores"""
        metrics = {}
        
        try:
            if not self.docker_client:
                return metrics
            
            # Obtener contenedores de WhatsApp
            whatsapp_containers = self.docker_client.containers.list(
                filters={'name': 'kreo-whatsapp'}
            )
            
            if not whatsapp_containers:
                return metrics
            
            # Métricas promedio de CPU
            cpu_usages = []
            memory_usages = []
            
            for container in whatsapp_containers:
                try:
                    stats = container.stats(stream=False)
                    
                    # Calcular uso de CPU
                    cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
                    system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
                    
                    if system_delta > 0:
                        cpu_percent = (cpu_delta / system_delta) * len(stats['cpu_stats']['cpu_usage']['percpu_usage'])
                        cpu_usages.append(cpu_percent)
                    
                    # Uso de memoria
                    memory_percent = (stats['memory_stats']['usage'] / stats['memory_stats']['limit']) * 100
                    memory_usages.append(memory_percent)
                    
                except Exception as e:
                    logger.warning(f"Error obteniendo stats de contenedor: {str(e)}")
            
            if cpu_usages:
                metrics['container_cpu_usage'] = sum(cpu_usages) / len(cpu_usages) / 100.0
            if memory_usages:
                metrics['container_memory_usage'] = sum(memory_usages) / len(memory_usages) / 100.0
            
            self.current_instances = len(whatsapp_containers)
            
        except Exception as e:
            logger.error(f"Error obteniendo métricas de contenedores: {str(e)}")
        
        return metrics
    
    def _make_scaling_decision(self, scale_up_score: float, scale_down_score: float, 
                              reasons: List[str], current_metrics: Dict[str, float]) -> ScalingDecision:
        """Tomar decisión de escalado"""
        current_time = time.time()
        
        # Lógica de decisión
        if scale_up_score >= 0.8:  # Alta puntuación para escalar arriba
            action = ScalingAction.SCALE_UP
            confidence = scale_up_score
            reason = f"Escala arriba: {'; '.join(reasons)}"
        elif scale_up_score >= 0.5:  # Puntuación moderada
            action = ScalingAction.SCALE_UP
            confidence = scale_up_score
            reason = f"Escala arriba (moderado): {'; '.join(reasons)}"
        elif scale_down_score >= 0.7 and self.current_instances > self.min_instances:
            action = ScalingAction.SCALE_DOWN
            confidence = scale_down_score
            reason = f"Escala abajo: {'; '.join(reasons)}"
        else:
            action = ScalingAction.NO_ACTION
            confidence = 0.0
            reason = "No se requiere escalado"
        
        return ScalingDecision(
            action=action,
            reason=reason,
            confidence=confidence,
            timestamp=current_time,
            current_metrics=current_metrics,
            recommended_instances=self._calculate_recommended_instances(action)
        )
    
    def _calculate_recommended_instances(self, action: ScalingAction) -> int:
        """Calcular número recomendado de instancias"""
        if action == ScalingAction.SCALE_UP:
            return min(self.current_instances + 1, self.max_instances)
        elif action == ScalingAction.SCALE_DOWN:
            return max(self.current_instances - 1, self.min_instances)
        elif action == ScalingAction.EMERGENCY_SCALE_UP:
            return min(self.current_instances + 2, self.max_instances)
        else:
            return self.current_instances
    
    @log_auto_scaling_event("INFO", "execute_scaling_action")
    @handle_auto_scaling_errors("execute_scaling_action")
    def _execute_scaling_action(self, decision: ScalingDecision):
        """Ejecutar acción de escalado"""
        try:
            logger.info(f"Ejecutando acción de escalado: {decision.action.value} - {decision.reason}")
            
            if decision.action == ScalingAction.SCALE_UP:
                self._scale_up(decision.recommended_instances)
            elif decision.action == ScalingAction.SCALE_DOWN:
                self._scale_down(decision.recommended_instances)
            elif decision.action == ScalingAction.EMERGENCY_SCALE_UP:
                self._emergency_scale_up(decision.recommended_instances)
            
            # Registrar decisión con logging estructurado
            log_event(
                "auto_scaling",
                "INFO",
                f"Acción de escalado ejecutada: {decision.action.value}",
                operation="scaling_action_executed",
                performance_metrics={
                    "action": decision.action.value,
                    "confidence": decision.confidence,
                    "reason": decision.reason
                },
                business_metrics={
                    "scaling_success": True,
                    "instances_changed": True
                },
                metadata={
                    "component": "auto_scaling_execution",
                    "recommended_instances": decision.recommended_instances,
                    "current_instances": self.current_instances
                }
            )
            
            # Registrar decisión
            self.scaling_history.append(decision)
            self.last_scaling_action = decision.timestamp
            
            # Limitar historial
            if len(self.scaling_history) > 100:
                self.scaling_history.pop(0)
                
        except Exception as e:
            log_error("auto_scaling", e, {
                "operation": "execute_scaling_action",
                "action": decision.action.value,
                "recommended_instances": decision.recommended_instances
            })
            logger.error(f"Error ejecutando acción de escalado: {str(e)}")
    
    def _scale_up(self, target_instances: int):
        """Escalar hacia arriba"""
        try:
            logger.info(f"Escalando hacia arriba: {self.current_instances} -> {target_instances} instancias")
            
            # Usar docker-compose para escalar
            result = subprocess.run([
                'docker-compose', '-f', 'compose.optimized-v2.yml', 'up', '-d',
                '--scale', f'kreo_whats2={target_instances}'
            ], capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                logger.info(f"Escalado exitoso a {target_instances} instancias")
                self.current_instances = target_instances
            else:
                logger.error(f"Error en escalado: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error ejecutando escalado: {str(e)}")
    
    def _scale_down(self, target_instances: int):
        """Escalar hacia abajo"""
        try:
            logger.info(f"Escalando hacia abajo: {self.current_instances} -> {target_instances} instancias")
            
            # Detener instancias adicionales
            if target_instances < self.current_instances:
                instances_to_stop = self.current_instances - target_instances
                
                # Obtener contenedores actuales
                if self.docker_client:
                    containers = self.docker_client.containers.list(
                        filters={'name': 'kreo-whatsapp'}
                    )
                    
                    # Detener instancias más recientes
                    for i, container in enumerate(containers[:instances_to_stop]):
                        try:
                            logger.info(f"Deteniendo contenedor: {container.name}")
                            container.stop(timeout=30)
                        except Exception as e:
                            logger.error(f"Error deteniendo contenedor {container.name}: {str(e)}")
            
            self.current_instances = target_instances
            
        except Exception as e:
            logger.error(f"Error ejecutando escalado hacia abajo: {str(e)}")
    
    def _emergency_scale_up(self, target_instances: int):
        """Escalado de emergencia"""
        try:
            logger.critical(f"ESCALADO DE EMERGENCIA: {self.current_instances} -> {target_instances} instancias")
            
            # Escalar rápidamente
            self._scale_up(target_instances)
            
            # Enviar alerta
            self._send_emergency_alert(target_instances)
            
        except Exception as e:
            logger.error(f"Error en escalado de emergencia: {str(e)}")
    
    def _send_emergency_alert(self, target_instances: int):
        """Enviar alerta de emergencia"""
        try:
            # Aquí se integraría con sistemas de alerta como Slack, PagerDuty, etc.
            alert_data = {
                'alert_type': 'emergency_scaling',
                'timestamp': time.time(),
                'current_instances': self.current_instances,
                'target_instances': target_instances,
                'reason': 'Circuit breaker open or critical error rate'
            }
            
            logger.critical(f"ALERTA DE EMERGENCIA: {json.dumps(alert_data)}")
            
        except Exception as e:
            logger.error(f"Error enviando alerta de emergencia: {str(e)}")
    
    def get_scaling_status(self) -> Dict[str, Any]:
        """Obtener estado actual de escalado"""
        return {
            'current_instances': self.current_instances,
            'max_instances': self.max_instances,
            'min_instances': self.min_instances,
            'last_scaling_action': self.last_scaling_action,
            'scaling_history': [
                {
                    'action': d.action.value,
                    'reason': d.reason,
                    'confidence': d.confidence,
                    'timestamp': d.timestamp,
                    'recommended_instances': d.recommended_instances
                }
                for d in self.scaling_history[-10:]  # Últimas 10 decisiones
            ],
            'current_metrics': self._get_current_metrics(),
            'scaling_rules': [
                {
                    'name': rule.name,
                    'metric': rule.metric,
                    'condition': rule.condition,
                    'threshold': rule.threshold,
                    'action': rule.action.value,
                    'weight': rule.weight
                }
                for rule in self.scaling_rules
            ]
        }
    
    def add_scaling_rule(self, rule: ScalingRule):
        """Agregar regla de escalado"""
        self.scaling_rules.append(rule)
        logger.info(f"Regla de escalado agregada: {rule.name}")
    
    def remove_scaling_rule(self, rule_name: str):
        """Remover regla de escalado"""
        self.scaling_rules = [r for r in self.scaling_rules if r.name != rule_name]
        logger.info(f"Regla de escalado removida: {rule_name}")

# Instancia global del gestor de auto-scaling
auto_scaling_manager = AutoScalingManager()

def get_scaling_status() -> Dict[str, Any]:
    """Función de conveniencia para obtener estado de escalado"""
    return auto_scaling_manager.get_scaling_status()

def trigger_manual_scaling(action: str, instances: int = None):
    """Función de conveniencia para escalado manual"""
    try:
        if action == 'scale_up':
            auto_scaling_manager._scale_up(instances or auto_scaling_manager.current_instances + 1)
        elif action == 'scale_down':
            auto_scaling_manager._scale_down(instances or auto_scaling_manager.current_instances - 1)
        elif action == 'emergency_scale_up':
            auto_scaling_manager._emergency_scale_up(instances or auto_scaling_manager.current_instances + 2)
    except Exception as e:
        logger.error(f"Error en escalado manual: {str(e)}")

def add_custom_scaling_rule(name: str, metric: str, condition: str, threshold: float, 
                           duration: int, action: str, weight: float = 1.0):
    """Función de conveniencia para agregar regla personalizada"""
    scaling_action = ScalingAction(action)
    rule = ScalingRule(
        name=name,
        metric=metric,
        condition=condition,
        threshold=threshold,
        duration=duration,
        action=scaling_action,
        weight=weight
    )
    auto_scaling_manager.add_scaling_rule(rule)