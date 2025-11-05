#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

"""
Integración con sistema de monitoreo y métricas para WhatsApp
Implementa métricas Prometheus, alertas y dashboards
"""

import time
import logging
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict
from frappe import _

from kreo_whats2.kreo_whats2.integration.redis_config import redis_manager
from kreo_whats2.kreo_whats2.integration.health_checker import health_checker
from kreo_whats2.kreo_whats2.integration.rate_limiter import rate_limiter
from kreo_whats2.kreo_whats2.integration.circuit_breaker import circuit_breaker_manager
from kreo_whats2.kreo_whats2.utils.logging_manager import get_logger, log_event, log_performance, log_error, logging_manager
from kreo_whats2.kreo_whats2.utils.log_analytics import analytics_engine, add_log_for_analysis
from kreo_whats2.kreo_whats2.utils.alert_manager import alert_manager, trigger_manual_alert

logger = get_logger("monitoring")

@dataclass
class Metric:
    """Representa una métrica de monitoreo"""
    name: str
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: str = "gauge"  # gauge, counter, histogram
    
    def to_prometheus_format(self) -> str:
        """Convertir a formato Prometheus"""
        labels_str = ""
        if self.labels:
            labels_str = "{" + ",".join([f'{k}="{v}"' for k, v in self.labels.items()]) + "}"
        
        return f"{self.name}{labels_str} {self.value} {int(self.timestamp * 1000)}"

@dataclass
class AlertRule:
    """Regla de alerta"""
    name: str
    metric: str
    condition: str  # ">", "<", ">=", "<=", "=="
    threshold: float
    duration: int  # segundos
    severity: str  # "critical", "warning", "info"
    labels: Dict[str, str] = field(default_factory=dict)

class MetricsCollector:
    """Colector de métricas para WhatsApp"""
    
    def __init__(self):
        self.metrics: Dict[str, List[Metric]] = defaultdict(list)
        self.alert_rules: List[AlertRule] = []
        self.redis_client = redis_manager.get_cache_client()
        self._setup_default_alerts()
        self._start_collection_thread()
    
    def _setup_default_alerts(self):
        """Configurar alertas por defecto"""
        self.alert_rules = [
            # Alta tasa de errores
            AlertRule(
                name="whatsapp_high_error_rate",
                metric="whatsapp_messages_error_rate",
                condition=">",
                threshold=0.1,  # 10% de errores
                duration=60,  # durante 60 segundos
                severity="critical",
                labels={"service": "whatsapp", "team": "platform"}
            ),
            
            # Cola de mensajes larga
            AlertRule(
                name="whatsapp_long_queue",
                metric="whatsapp_queue_size",
                condition=">",
                threshold=1000,
                duration=120,
                severity="warning",
                labels={"service": "whatsapp", "component": "queue"}
            ),
            
            # Circuit breaker abierto
            AlertRule(
                name="whatsapp_circuit_breaker_open",
                metric="whatsapp_circuit_breaker_state",
                condition="==",
                threshold=1,  # 1 = OPEN
                duration=30,
                severity="critical",
                labels={"service": "whatsapp", "component": "circuit_breaker"}
            ),
            
            # Rate limiting excesivo
            AlertRule(
                name="whatsapp_rate_limit_exceeded",
                metric="whatsapp_rate_limit_rejections",
                condition=">",
                threshold=50,  # 50 rechazos por minuto
                duration=60,
                severity="warning",
                labels={"service": "whatsapp", "component": "rate_limiter"}
            ),
            
            # Redis connection issues
            AlertRule(
                name="whatsapp_redis_connection_issues",
                metric="whatsapp_redis_connection_errors",
                condition=">",
                threshold=5,
                duration=60,
                severity="critical",
                labels={"service": "whatsapp", "component": "redis"}
            )
        ]
    
    def _start_collection_thread(self):
        """Iniciar hilo de recolección de métricas"""
        def collect_metrics():
            while True:
                try:
                    self._collect_system_metrics()
                    time.sleep(30)  # Recolectar cada 30 segundos
                except Exception as e:
                    logger.error(f"Error en recolección de métricas: {str(e)}")
                    time.sleep(60)  # Esperar más tiempo en caso de error
        
        thread = threading.Thread(target=collect_metrics, daemon=True)
        thread.start()
        logger.info("Hilo de recolección de métricas iniciado")
    
    def _collect_system_metrics(self):
        """Recolectar métricas del sistema con logging estructurado avanzado"""
        timestamp = time.time()
        
        # Iniciar contexto de operación para seguimiento de performance
        correlation_id = logging_manager.start_operation_context(
            "system_metrics_collection",
            metadata={"collection_type": "system", "timestamp": timestamp}
        )
        
        # Métricas de Redis
        try:
            pool_stats = redis_manager.get_pool_stats()
            redis_metrics_count = 0
            
            for pool_name, stats in pool_stats.items():
                if 'error' not in stats:
                    # Métricas de conexión
                    self.add_metric(Metric(
                        name="whatsapp_redis_pool_connections",
                        value=stats['total_connections'],
                        timestamp=timestamp,
                        labels={'pool': pool_name, 'type': 'total'}
                    ))
                    
                    self.add_metric(Metric(
                        name="whatsapp_redis_pool_connections",
                        value=stats['in_use_connections'],
                        timestamp=timestamp,
                        labels={'pool': pool_name, 'type': 'in_use'}
                    ))
                    
                    self.add_metric(Metric(
                        name="whatsapp_redis_pool_connection_ratio",
                        value=stats['connection_ratio'],
                        timestamp=timestamp,
                        labels={'pool': pool_name}
                    ))
                    
                    # Enviar métricas a Log Analytics para análisis
                    analytics_data = {
                        "@timestamp": datetime.now().isoformat(),
                        "level": "INFO",
                        "service": "kreo_whats2",
                        "operation": "redis_metrics",
                        "pool_name": pool_name,
                        "performance_metrics": {
                            "total_connections": stats['total_connections'],
                            "in_use_connections": stats['in_use_connections'],
                            "connection_ratio": stats['connection_ratio'],
                            "collection_timestamp": timestamp
                        },
                        "business_metrics": {
                            "pool_health_score": stats['connection_ratio'] * 100
                        },
                        "metadata": {
                            "component": "redis_monitoring",
                            "metric_source": "prometheus_collector"
                        }
                    }
                    
                    # Registrar evento de logging estructurado avanzado
                    log_event(
                        "monitoring",
                        "INFO",
                        f"Métricas Redis recolectadas para pool {pool_name}",
                        operation="redis_metrics_collection",
                        performance_metrics={
                            "total_connections": stats['total_connections'],
                            "in_use_connections": stats['in_use_connections'],
                            "connection_ratio": stats['connection_ratio']
                        },
                        business_metrics={
                            "pool_health_score": stats['connection_ratio'] * 100
                        },
                        metadata={
                            "pool_name": pool_name,
                            "component": "redis_monitoring",
                            "correlation_id": correlation_id
                        }
                    )
                    
                    # Enviar al motor de analytics para detección de patrones
                    add_log_for_analysis(analytics_data)
                    redis_metrics_count += 1
                    
            # Registrar métricas recolectadas
            self.add_metric(Metric(
                name="whatsapp_redis_pools_monitored",
                value=redis_metrics_count,
                timestamp=timestamp
            ))
            
        except Exception as e:
            logger.error(f"Error recolectando métricas de Redis: {str(e)}")
            log_error("monitoring", e, {
                "operation": "redis_metrics_collection",
                "pool_name": pool_name if 'pool_name' in locals() else "unknown",
                "correlation_id": correlation_id
            })
            # Enviar alerta al Alert Manager
            trigger_manual_alert("whatsapp_redis_connection_issues", f"Error en recolección de métricas Redis: {str(e)}")
        
        # Métricas de health checks con logging avanzado
        try:
            health_status = health_checker.get_status_summary()
            status_map = {'healthy': 0, 'degraded': 1, 'unhealthy': 2, 'no_checks_run': 3}
            status_value = status_map.get(health_status.get('overall_status', 'unknown'), 3)
            
            self.add_metric(Metric(
                name="whatsapp_health_status",
                value=status_value,
                timestamp=timestamp,
                labels={'status': health_status.get('overall_status', 'unknown')}
            ))
            
            self.add_metric(Metric(
                name="whatsapp_healthy_services",
                value=health_status.get('healthy_services', 0),
                timestamp=timestamp
            ))
            
            # Logging estructurado para health checks
            log_event(
                "monitoring",
                "INFO",
                "Métricas de health check recolectadas",
                operation="health_check_metrics",
                performance_metrics={
                    "overall_status_value": status_value,
                    "healthy_services": health_status.get('healthy_services', 0),
                    "total_services": health_status.get('total_services', 0),
                    "degraded_services": health_status.get('degraded_services', 0),
                    "unhealthy_services": health_status.get('unhealthy_services', 0)
                },
                business_metrics={
                    "system_health_score": (health_status.get('healthy_services', 0) / max(health_status.get('total_services', 1), 1)) * 100
                },
                metadata={
                    "component": "health_monitoring",
                    "correlation_id": correlation_id
                }
            )
            
            # Enviar al analytics engine
            add_log_for_analysis({
                "@timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "service": "kreo_whats2",
                "operation": "health_check_metrics",
                "performance_metrics": {
                    "overall_status_value": status_value,
                    "healthy_services": health_status.get('healthy_services', 0),
                    "total_services": health_status.get('total_services', 0)
                },
                "business_metrics": {
                    "system_health_score": (health_status.get('healthy_services', 0) / max(health_status.get('total_services', 1), 1)) * 100
                },
                "metadata": {
                    "component": "health_monitoring",
                    "metric_source": "prometheus_collector"
                }
            })
            
        except Exception as e:
            logger.error(f"Error recolectando métricas de health check: {str(e)}")
            log_error("monitoring", e, {
                "operation": "health_check_metrics_collection",
                "correlation_id": correlation_id
            })
            trigger_manual_alert("whatsapp_health_check_failure", f"Error en health check: {str(e)}")
        
        # Métricas de rate limiting con logging avanzado
        try:
            rate_stats = rate_limiter.get_global_stats()
            
            self.add_metric(Metric(
                name="whatsapp_rate_limit_current",
                value=rate_stats.get('current_limit', 10),
                timestamp=timestamp
            ))
            
            self.add_metric(Metric(
                name="whatsapp_rate_limit_burst",
                value=rate_stats.get('current_burst', 20),
                timestamp=timestamp
            ))
            
            self.add_metric(Metric(
                name="whatsapp_rate_limit_global_usage",
                value=rate_stats.get('global_usage_percentage', 0),
                timestamp=timestamp
            ))
            
            # Logging estructurado para rate limiting
            usage_percentage = rate_stats.get('global_usage_percentage', 0)
            if usage_percentage > 80:
                log_level = "WARNING"
                alert_needed = True
            else:
                log_level = "INFO"
                alert_needed = False
            
            log_event(
                "monitoring",
                log_level,
                f"Métricas de rate limiting - Uso: {usage_percentage}%",
                operation="rate_limit_metrics",
                performance_metrics={
                    "current_limit": rate_stats.get('current_limit', 10),
                    "current_burst": rate_stats.get('current_burst', 20),
                    "global_usage_percentage": usage_percentage,
                    "remaining_capacity": 100 - usage_percentage
                },
                business_metrics={
                    "rate_limit_efficiency": usage_percentage,
                    "capacity_utilization": usage_percentage / 100
                },
                metadata={
                    "component": "rate_limit_monitoring",
                    "correlation_id": correlation_id,
                    "alert_triggered": alert_needed
                }
            )
            
            # Enviar al analytics engine
            add_log_for_analysis({
                "@timestamp": datetime.now().isoformat(),
                "level": log_level,
                "service": "kreo_whats2",
                "operation": "rate_limit_metrics",
                "performance_metrics": {
                    "current_limit": rate_stats.get('current_limit', 10),
                    "current_burst": rate_stats.get('current_burst', 20),
                    "global_usage_percentage": usage_percentage
                },
                "business_metrics": {
                    "rate_limit_efficiency": usage_percentage,
                    "capacity_utilization": usage_percentage / 100
                },
                "metadata": {
                    "component": "rate_limit_monitoring",
                    "metric_source": "prometheus_collector",
                    "alert_needed": alert_needed
                }
            })
            
            # Disparar alerta si es necesario
            if alert_needed:
                trigger_manual_alert("whatsapp_rate_limit_exceeded", f"Uso de rate limit excedido: {usage_percentage}%")
                
        except Exception as e:
            logger.error(f"Error recolectando métricas de rate limiting: {str(e)}")
            log_error("monitoring", e, {
                "operation": "rate_limit_metrics_collection",
                "correlation_id": correlation_id
            })
            trigger_manual_alert("whatsapp_rate_limit_failure", f"Error en recolección de rate limit: {str(e)}")
        
        # Métricas de circuit breakers con logging avanzado
        try:
            circuit_states = circuit_breaker_manager.get_all_states()
            
            for breaker_name, state in circuit_states.items():
                state_map = {'closed': 0, 'open': 1, 'half_open': 2}
                state_value = state_map.get(state['state'], 3)
                
                self.add_metric(Metric(
                    name="whatsapp_circuit_breaker_state",
                    value=state_value,
                    timestamp=timestamp,
                    labels={'breaker': breaker_name}
                ))
                
                self.add_metric(Metric(
                    name="whatsapp_circuit_breaker_failure_rate",
                    value=state.get('failure_rate', 0),
                    timestamp=timestamp,
                    labels={'breaker': breaker_name}
                ))
                
                # Logging estructurado para circuit breakers
                if state_value == 1:  # Circuit breaker abierto
                    log_level = "CRITICAL"
                    alert_needed = True
                elif state_value == 2:  # Circuit breaker semi-abierto
                    log_level = "WARNING"
                    alert_needed = True
                else:
                    log_level = "INFO"
                    alert_needed = False
                
                log_event(
                    "monitoring",
                    log_level,
                    f"Estado de circuit breaker {breaker_name}: {state['state']}",
                    operation="circuit_breaker_metrics",
                    performance_metrics={
                        "breaker_state": state_value,
                        "failure_rate": state.get('failure_rate', 0),
                        "last_failure_time": state.get('last_failure_time', 0),
                        "success_count": state.get('success_count', 0),
                        "failure_count": state.get('failure_count', 0)
                    },
                    business_metrics={
                        "breaker_health_score": (1 - state_value / 3) * 100,  # Puntuación de salud
                        "circuit_status": state['state']
                    },
                    metadata={
                        "component": "circuit_breaker_monitoring",
                        "breaker_name": breaker_name,
                        "correlation_id": correlation_id,
                        "alert_triggered": alert_needed
                    }
                )
                
                # Enviar al analytics engine
                add_log_for_analysis({
                    "@timestamp": datetime.now().isoformat(),
                    "level": log_level,
                    "service": "kreo_whats2",
                    "operation": "circuit_breaker_metrics",
                    "breaker_name": breaker_name,
                    "performance_metrics": {
                        "breaker_state": state_value,
                        "failure_rate": state.get('failure_rate', 0),
                        "last_failure_time": state.get('last_failure_time', 0),
                        "success_count": state.get('success_count', 0),
                        "failure_count": state.get('failure_count', 0)
                    },
                    "business_metrics": {
                        "breaker_health_score": (1 - state_value / 3) * 100,
                        "circuit_status": state['state']
                    },
                    "metadata": {
                        "component": "circuit_breaker_monitoring",
                        "breaker_name": breaker_name,
                        "metric_source": "prometheus_collector",
                        "alert_needed": alert_needed
                    }
                })
                
                # Disparar alerta si el circuit breaker está abierto
                if alert_needed:
                    trigger_manual_alert("whatsapp_circuit_breaker_open", f"Circuit breaker {breaker_name} en estado: {state['state']}")
                    
        except Exception as e:
            logger.error(f"Error recolectando métricas de circuit breakers: {str(e)}")
            log_error("monitoring", e, {
                "operation": "circuit_breaker_metrics_collection",
                "correlation_id": correlation_id
            })
            trigger_manual_alert("whatsapp_circuit_breaker_failure", f"Error en recolección de circuit breakers: {str(e)}")
        
        # Métricas de WhatsApp específicas
        try:
            self._collect_whatsapp_specific_metrics(timestamp, correlation_id)
        except Exception as e:
            logger.error(f"Error recolectando métricas específicas de WhatsApp: {str(e)}")
            log_error("monitoring", e, {
                "operation": "whatsapp_specific_metrics_collection",
                "correlation_id": correlation_id
            })
            trigger_manual_alert("whatsapp_specific_metrics_failure", f"Error en recolección de métricas WhatsApp: {str(e)}")
    
    def _collect_whatsapp_specific_metrics(self, timestamp: float, correlation_id: str):
        """Recolectar métricas específicas de WhatsApp con logging estructurado"""
        try:
            # Obtener estadísticas de cola desde Redis
            queue_client = redis_manager.get_queue_client()
            if queue_client:
                queue_size = queue_client.llen('kreo_whatsapp_queue')
                
                self.add_metric(Metric(
                    name="whatsapp_queue_size",
                    value=queue_size,
                    timestamp=timestamp
                ))
                
                # Logging estructurado para métricas de cola
                if queue_size > 1000:
                    log_level = "WARNING"
                    alert_needed = True
                else:
                    log_level = "INFO"
                    alert_needed = False
                
                log_event(
                    "monitoring",
                    log_level,
                    f"Métricas de cola WhatsApp - Tamaño: {queue_size}",
                    operation="whatsapp_queue_metrics",
                    performance_metrics={
                        "queue_size": queue_size,
                        "queue_growth_rate": getattr(self, '_calculate_queue_growth', lambda: 0)(),
                        "avg_processing_time": getattr(self, '_get_avg_processing_time', lambda: 0)()
                    },
                    business_metrics={
                        "queue_health_score": max(0, 100 - (queue_size / 10)),  # Puntuación de salud inversamente proporcional al tamaño
                        "backlog_severity": "high" if queue_size > 1000 else "normal"
                    },
                    metadata={
                        "component": "whatsapp_queue_monitoring",
                        "correlation_id": correlation_id,
                        "alert_triggered": alert_needed
                    }
                )
                
                # Enviar al analytics engine
                add_log_for_analysis({
                    "@timestamp": datetime.now().isoformat(),
                    "level": log_level,
                    "service": "kreo_whats2",
                    "operation": "whatsapp_queue_metrics",
                    "performance_metrics": {
                        "queue_size": queue_size
                    },
                    "business_metrics": {
                        "queue_health_score": max(0, 100 - (queue_size / 10)),
                        "backlog_severity": "high" if queue_size > 1000 else "normal"
                    },
                    "metadata": {
                        "component": "whatsapp_queue_monitoring",
                        "metric_source": "prometheus_collector",
                        "alert_needed": alert_needed
                    }
                })
                
                # Disparar alerta si la cola es muy grande
                if alert_needed:
                    trigger_manual_alert("whatsapp_long_queue", f"Cola de WhatsApp muy larga: {queue_size} mensajes")
                
                # Estadísticas diarias
                today = datetime.now().strftime('%Y-%m-%d')
                stats_key = f"whatsapp_queue_stats:{today}"
                stats = queue_client.hgetall(stats_key)
                
                if stats:
                    stats_dict = {k.decode(): int(v.decode()) for k, v in stats.items()}
                    
                    processed = stats_dict.get('processed', 0)
                    failed = stats_dict.get('failed', 0)
                    total = processed + failed
                    
                    if total > 0:
                        error_rate = failed / total
                        
                        self.add_metric(Metric(
                            name="whatsapp_messages_processed_today",
                            value=processed,
                            timestamp=timestamp
                        ))
                        
                        self.add_metric(Metric(
                            name="whatsapp_messages_failed_today",
                            value=failed,
                            timestamp=timestamp
                        ))
                        
                        self.add_metric(Metric(
                            name="whatsapp_messages_error_rate",
                            value=error_rate,
                            timestamp=timestamp
                        ))
                        
                        # Logging estructurado para métricas de mensajes
                        log_event(
                            "monitoring",
                            "INFO",
                            f"Estadísticas diarias WhatsApp - Procesados: {processed}, Fallidos: {failed}, Tasa de error: {error_rate:.2%}",
                            operation="whatsapp_daily_stats",
                            performance_metrics={
                                "messages_processed": processed,
                                "messages_failed": failed,
                                "error_rate": error_rate,
                                "success_rate": 1 - error_rate
                            },
                            business_metrics={
                                "daily_throughput": processed + failed,
                                "service_quality_score": (1 - error_rate) * 100,
                                "reliability_percentage": (1 - error_rate) * 100
                            },
                            metadata={
                                "component": "whatsapp_daily_monitoring",
                                "correlation_id": correlation_id,
                                "date": today
                            }
                        )
                        
                        # Enviar al analytics engine
                        add_log_for_analysis({
                            "@timestamp": datetime.now().isoformat(),
                            "level": "INFO",
                            "service": "kreo_whats2",
                            "operation": "whatsapp_daily_stats",
                            "performance_metrics": {
                                "messages_processed": processed,
                                "messages_failed": failed,
                                "error_rate": error_rate,
                                "success_rate": 1 - error_rate
                            },
                            "business_metrics": {
                                "daily_throughput": processed + failed,
                                "service_quality_score": (1 - error_rate) * 100,
                                "reliability_percentage": (1 - error_rate) * 100
                            },
                            "metadata": {
                                "component": "whatsapp_daily_monitoring",
                                "metric_source": "prometheus_collector",
                                "date": today
                            }
                        })
                        
                        # Disparar alerta si la tasa de error es alta
                        if error_rate > 0.1:  # Más del 10% de errores
                            trigger_manual_alert("whatsapp_high_error_rate", f"Tasa de errores alta en WhatsApp: {error_rate:.2%}")
                            
        except Exception as e:
            logger.error(f"Error recolectando métricas específicas de WhatsApp: {str(e)}")
            log_error("monitoring", e, {
                "operation": "whatsapp_specific_metrics_collection",
                "correlation_id": correlation_id
            })
            trigger_manual_alert("whatsapp_specific_metrics_failure", f"Error en recolección de métricas WhatsApp: {str(e)}")
    
    def _calculate_queue_growth(self) -> float:
        """Calcular tasa de crecimiento de la cola (implementación simplificada)"""
        try:
            # Implementación simplificada - en producción usaría datos históricos
            return 0.0
        except:
            return 0.0
    
    def _get_avg_processing_time(self) -> float:
        """Obtener tiempo promedio de procesamiento (implementación simplificada)"""
        try:
            # Implementación simplificada - en producción usaría datos reales
            return 1000.0  # milisegundos
        except:
            return 1000.0
    
    def add_metric(self, metric: Metric):
        """Agregar métrica al colector"""
        # Limitar el número de métricas almacenadas en memoria
        max_metrics = 1000
        if len(self.metrics[metric.name]) >= max_metrics:
            self.metrics[metric.name].pop(0)
        
        self.metrics[metric.name].append(metric)
        
        # Guardar en Redis para persistencia
        self._save_metric_to_redis(metric)
    
    def _save_metric_to_redis(self, metric: Metric):
        """Guardar métrica en Redis"""
        try:
            if not self.redis_client:
                return
            
            metric_key = f"metrics:{metric.name}:{int(metric.timestamp)}"
            metric_data = {
                'value': metric.value,
                'labels': metric.labels,
                'timestamp': metric.timestamp
            }
            
            # Guardar con expiración de 24 horas
            self.redis_client.setex(metric_key, 86400, json.dumps(metric_data))
            
        except Exception as e:
            logger.warning(f"Error guardando métrica en Redis: {str(e)}")
    
    def get_metrics_for_prometheus(self) -> str:
        """Obtener métricas en formato Prometheus"""
        metrics_text = []
        
        # Métricas actuales
        for metric_list in self.metrics.values():
            if metric_list:
                latest_metric = metric_list[-1]
                metrics_text.append(latest_metric.to_prometheus_format())
        
        # Métricas desde Redis (últimos 5 minutos)
        try:
            if self.redis_client:
                five_minutes_ago = int(time.time()) - 300
                pattern = f"metrics:*:{five_minutes_ago}*"
                
                for key in self.redis_client.scan_iter(match=pattern):
                    try:
                        data = self.redis_client.get(key)
                        if data:
                            metric_data = json.loads(data)
                            metric_name = key.decode().split(':', 2)[1]
                            
                            metric = Metric(
                                name=metric_name,
                                value=metric_data['value'],
                                timestamp=metric_data['timestamp'],
                                labels=metric_data['labels']
                            )
                            metrics_text.append(metric.to_prometheus_format())
                    except:
                        continue
        except Exception as e:
            logger.warning(f"Error obteniendo métricas desde Redis: {str(e)}")
        
        return "\n".join(metrics_text)
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """Verificar alertas activas"""
        active_alerts = []
        current_time = time.time()
        
        for rule in self.alert_rules:
            try:
                # Obtener métricas recientes para la regla
                recent_metrics = self._get_recent_metrics(rule.metric, 300)  # Últimos 5 minutos
                
                if recent_metrics:
                    latest_value = recent_metrics[-1].value
                    
                    # Evaluar condición
                    condition_met = False
                    if rule.condition == ">" and latest_value > rule.threshold:
                        condition_met = True
                    elif rule.condition == "<" and latest_value < rule.threshold:
                        condition_met = True
                    elif rule.condition == ">=" and latest_value >= rule.threshold:
                        condition_met = True
                    elif rule.condition == "<=" and latest_value <= rule.threshold:
                        condition_met = True
                    elif rule.condition == "==" and latest_value == rule.threshold:
                        condition_met = True
                    
                    if condition_met:
                        alert = {
                            'rule_name': rule.name,
                            'metric': rule.metric,
                            'current_value': latest_value,
                            'threshold': rule.threshold,
                            'condition': rule.condition,
                            'severity': rule.severity,
                            'timestamp': current_time,
                            'labels': rule.labels
                        }
                        active_alerts.append(alert)
                        
            except Exception as e:
                logger.error(f"Error verificando alerta {rule.name}: {str(e)}")
        
        return active_alerts
    
    def _get_recent_metrics(self, metric_name: str, time_window: int) -> List[Metric]:
        """Obtener métricas recientes para un nombre específico"""
        recent_metrics = []
        cutoff_time = time.time() - time_window
        
        # Desde memoria
        if metric_name in self.metrics:
            recent_metrics.extend([
                m for m in self.metrics[metric_name]
                if m.timestamp >= cutoff_time
            ])
        
        # Desde Redis
        try:
            if self.redis_client:
                pattern = f"metrics:{metric_name}:*"
                for key in self.redis_client.scan_iter(match=pattern):
                    try:
                        data = self.redis_client.get(key)
                        if data:
                            metric_data = json.loads(data)
                            if metric_data['timestamp'] >= cutoff_time:
                                metric = Metric(
                                    name=metric_name,
                                    value=metric_data['value'],
                                    timestamp=metric_data['timestamp'],
                                    labels=metric_data['labels']
                                )
                                recent_metrics.append(metric)
                    except:
                        continue
        except Exception as e:
            logger.warning(f"Error obteniendo métricas recientes desde Redis: {str(e)}")
        
        # Ordenar por timestamp
        recent_metrics.sort(key=lambda x: x.timestamp)
        return recent_metrics
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Obtener datos para dashboard"""
        current_time = time.time()
        
        return {
            'timestamp': current_time,
            'health_status': health_checker.get_status_summary(),
            'rate_limit_stats': rate_limiter.get_global_stats(),
            'circuit_breaker_states': circuit_breaker_manager.get_all_states(),
            'recent_alerts': self.check_alerts(),
            'queue_metrics': self._get_queue_metrics(),
            'performance_metrics': self._get_performance_metrics()
        }
    
    def _get_queue_metrics(self) -> Dict[str, Any]:
        """Obtener métricas de cola"""
        try:
            queue_client = redis_manager.get_queue_client()
            if queue_client:
                queue_size = queue_client.llen('kreo_whatsapp_queue')
                
                # Obtener estadísticas de procesamiento
                processing_stats = queue_client.hgetall('whatsapp_processing_stats')
                
                return {
                    'queue_size': queue_size,
                    'processing_stats': {k.decode(): int(v.decode()) for k, v in processing_stats.items()} if processing_stats else {}
                }
        except Exception as e:
            logger.error(f"Error obteniendo métricas de cola: {str(e)}")
        
        return {'queue_size': 0, 'processing_stats': {}}
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Obtener métricas de performance"""
        try:
            # Obtener métricas de performance desde Redis
            if self.redis_client:
                perf_data = self.redis_client.hgetall('whatsapp_performance')
                return {k.decode(): float(v.decode()) for k, v in perf_data.items()} if perf_data else {}
        except Exception as e:
            logger.error(f"Error obteniendo métricas de performance: {str(e)}")
        
        return {}

# Instancia global del colector de métricas
metrics_collector = MetricsCollector()

def get_prometheus_metrics() -> str:
    """Función de conveniencia para obtener métricas Prometheus"""
    return metrics_collector.get_metrics_for_prometheus()

def check_active_alerts() -> List[Dict[str, Any]]:
    """Función de conveniencia para verificar alertas"""
    return metrics_collector.check_alerts()

def get_dashboard_data() -> Dict[str, Any]:
    """Función de conveniencia para obtener datos de dashboard"""
    return metrics_collector.get_dashboard_data()

def add_custom_metric(name: str, value: float, labels: Dict[str, str] = None, metric_type: str = "gauge"):
    """Función de conveniencia para agregar métrica personalizada"""
    metric = Metric(
        name=name,
        value=value,
        timestamp=time.time(),
        labels=labels or {},
        metric_type=metric_type
    )
    metrics_collector.add_metric(metric)

def sync_kpis_with_analytics():
    """Sincronizar KPIs entre Prometheus y Log Analytics"""
    try:
        # Obtener métricas clave del colector
        kpi_metrics = [
            'whatsapp_queue_size',
            'whatsapp_messages_error_rate',
            'whatsapp_messages_processed_today',
            'whatsapp_health_status',
            'whatsapp_rate_limit_global_usage'
        ]
        
        kpi_data = {}
        for metric_name in kpi_metrics:
            if metric_name in metrics_collector.metrics:
                latest_metric = metrics_collector.metrics[metric_name][-1]
                kpi_data[metric_name] = {
                    'value': latest_metric.value,
                    'timestamp': latest_metric.timestamp,
                    'labels': latest_metric.labels
                }
        
        # Enviar KPIs al analytics engine
        add_log_for_analysis({
            "@timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "service": "kreo_whats2",
            "operation": "kpi_sync",
            "kpi_metrics": kpi_data,
            "sync_type": "prometheus_to_analytics",
            "metadata": {
                "component": "kpi_synchronization",
                "source": "prometheus_collector",
                "target": "log_analytics"
            }
        })
        
        # Logging estructurado para la sincronización de KPIs
        log_event(
            "monitoring",
            "INFO",
            f"KPIs sincronizados con Log Analytics - Métricas: {len(kpi_data)}",
            operation="kpi_synchronization",
            performance_metrics={
                "kpi_count": len(kpi_data),
                "sync_timestamp": time.time(),
                "metrics_synced": list(kpi_data.keys())
            },
            business_metrics={
                "data_consistency_score": 100,  # Suponiendo consistencia perfecta
                "sync_success_rate": 1.0
            },
            metadata={
                "component": "kpi_synchronization",
                "sync_direction": "prometheus_to_analytics"
            }
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error sincronizando KPIs con analytics: {str(e)}")
        log_error("monitoring", e, {
            "operation": "kpi_synchronization",
            "sync_direction": "prometheus_to_analytics"
        })
        return False

def trigger_alert_to_both_systems(alert_name: str, message: str, severity: str = "warning"):
    """Disparar alerta en ambos sistemas (Prometheus y Alert Manager)"""
    try:
        # Disparar alerta en Alert Manager
        trigger_manual_alert(alert_name, message)
        
        # Enviar evento de alerta al analytics engine para correlación
        add_log_for_analysis({
            "@timestamp": datetime.now().isoformat(),
            "level": severity.upper(),
            "service": "kreo_whats2",
            "operation": "alert_trigger",
            "alert_name": alert_name,
            "message": message,
            "severity": severity,
            "metadata": {
                "component": "alert_correlation",
                "source": "prometheus_collector",
                "target": "alert_manager"
            }
        })
        
        # Logging estructurado para la alerta
        log_event(
            "monitoring",
            severity.upper(),
            f"Alerta disparada: {alert_name} - {message}",
            operation="alert_trigger",
            performance_metrics={
                "alert_name": alert_name,
                "severity": severity,
                "trigger_timestamp": time.time()
            },
            business_metrics={
                "alert_impact_score": 50 if severity == "warning" else 100
            },
            metadata={
                "component": "alert_correlation",
                "alert_source": "prometheus_collector"
            }
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error disparando alerta en ambos sistemas: {str(e)}")
        log_error("monitoring", e, {
            "operation": "alert_trigger",
            "alert_name": alert_name
        })
        return False