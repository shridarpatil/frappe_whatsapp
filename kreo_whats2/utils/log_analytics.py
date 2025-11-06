#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

"""
Sistema de análisis de logs y métricas para WhatsApp
Implementa análisis de patrones, tendencias y KPIs basados en logs estructurados
"""

import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import threading
import time
import statistics
from frappe import _

from kreo_whats2.kreo_whats2.utils.logging_manager import logging_manager, LogContext

logger = logging_manager.get_logger("log_analytics")

@dataclass
class LogPattern:
    """Patrón detectado en los logs"""
    pattern_id: str
    name: str
    description: str
    severity: str  # info, warning, critical
    frequency: int
    last_occurrence: str
    affected_operations: List[str]
    suggested_actions: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BusinessMetric:
    """Métrica de negocio calculada"""
    name: str
    value: float
    unit: str
    trend: str  # up, down, stable
    timestamp: str
    comparison_period: str
    metadata: Dict[str, Any] = field(default_factory=dict)

class LogAnalyticsEngine:
    """Motor de análisis de logs para detección de patrones y métricas"""
    
    def __init__(self):
        self.patterns: List[LogPattern] = []
        self.business_metrics: Dict[str, BusinessMetric] = {}
        self.log_buffer: List[Dict[str, Any]] = []
        self.analysis_window = 300  # 5 minutos
        self._start_analysis_engine()
        self._load_known_patterns()
    
    def _start_analysis_engine(self):
        """Iniciar motor de análisis en segundo plano"""
        def analyze_logs():
            while True:
                try:
                    self._perform_analysis()
                    time.sleep(60)  # Analizar cada minuto
                except Exception as e:
                    logger.error(f"Error en motor de análisis: {str(e)}")
                    time.sleep(120)
        
        thread = threading.Thread(target=analyze_logs, daemon=True)
        thread.start()
        logger.info("Motor de análisis de logs iniciado")
    
    def _load_known_patterns(self):
        """Cargar patrones conocidos para detección"""
        self.known_patterns = {
            "high_error_rate": {
                "name": "Tasa de errores alta",
                "description": "Más del 10% de operaciones fallan en un periodo corto",
                "severity": "critical",
                "threshold": 0.1,
                "window_minutes": 5
            },
            "performance_degradation": {
                "name": "Degración de performance",
                "description": "Tiempo de respuesta promedio aumenta significativamente",
                "severity": "warning", 
                "threshold": 1.5,  # 50% más lento
                "window_minutes": 10
            },
            "unusual_activity": {
                "name": "Actividad inusual",
                "description": "Patrón de actividad fuera de lo normal",
                "severity": "info",
                "threshold": 3,  # 3 desviaciones estándar
                "window_minutes": 15
            },
            "security_anomaly": {
                "name": "Anomalía de seguridad",
                "description": "Eventos de seguridad inusuales detectados",
                "severity": "critical",
                "threshold": 5,  # 5 eventos en corto tiempo
                "window_minutes": 10
            }
        }
    
    def add_log_entry(self, log_data: Dict[str, Any]):
        """Agregar entrada de log para análisis"""
        try:
            # Limpiar buffer de logs antiguos
            cutoff_time = datetime.now() - timedelta(seconds=self.analysis_window)
            self.log_buffer = [
                log for log in self.log_buffer
                if datetime.fromisoformat(log.get("@timestamp", "2000-01-01T00:00:00")).replace(tzinfo=None) > cutoff_time
            ]
            
            # Agregar nuevo log
            self.log_buffer.append(log_data)
            
        except Exception as e:
            logger.error(f"Error agregando entrada de log: {str(e)}")
    
    def _perform_analysis(self):
        """Realizar análisis de patrones y tendencias"""
        try:
            if len(self.log_buffer) < 10:  # Necesitamos suficientes datos
                return
            
            # Análisis de tasa de errores
            self._analyze_error_rate()
            
            # Análisis de performance
            self._analyze_performance()
            
            # Análisis de actividad
            self._analyze_activity_patterns()
            
            # Análisis de seguridad
            self._analyze_security_events()
            
            # Calcular métricas de negocio
            self._calculate_business_metrics()
            
        except Exception as e:
            logger.error(f"Error en análisis de logs: {str(e)}")
    
    def _analyze_error_rate(self):
        """Analizar tasa de errores y detectar patrones"""
        try:
            # Obtener logs de error en la ventana de tiempo
            error_logs = [
                log for log in self.log_buffer
                if log.get("level") in ["ERROR", "CRITICAL"]
            ]
            
            if len(error_logs) == 0:
                return
            
            # Calcular tasa de errores por operación
            operation_errors = defaultdict(int)
            total_operations = defaultdict(int)
            
            for log in self.log_buffer:
                operation = log.get("operation", "unknown")
                total_operations[operation] += 1
                if log.get("level") in ["ERROR", "CRITICAL"]:
                    operation_errors[operation] += 1
            
            # Detectar operaciones con alta tasa de errores
            for operation, total in total_operations.items():
                if total > 5:  # Mínimo de operaciones para considerar
                    error_rate = operation_errors[operation] / total
                    if error_rate > self.known_patterns["high_error_rate"]["threshold"]:
                        self._create_pattern_alert(
                            "high_error_rate",
                            f"Alta tasa de errores en operación: {operation}",
                            error_rate,
                            operation
                        )
                        
        except Exception as e:
            logger.error(f"Error analizando tasa de errores: {str(e)}")
    
    def _analyze_performance(self):
        """Analizar métricas de performance y detectar degradación"""
        try:
            # Obtener logs de performance
            perf_logs = [
                log for log in self.log_buffer
                if log.get("operation") == "performance" and "performance_metrics" in log
            ]
            
            if len(perf_logs) < 5:
                return
            
            # Analizar tiempos de respuesta por operación
            operation_times = defaultdict(list)
            for log in perf_logs:
                operation = log.get("operation", "unknown")
                perf_metrics = log.get("performance_metrics", {})
                if "response_time_ms" in perf_metrics:
                    operation_times[operation].append(perf_metrics["response_time_ms"])
            
            # Detectar degradación de performance
            for operation, times in operation_times.items():
                if len(times) > 3:
                    current_avg = statistics.mean(times)
                    current_std = statistics.stdev(times) if len(times) > 1 else 0
                    
                    # Comparar con métricas históricas (simplificado)
                    historical_avg = getattr(self, f"_{operation}_historical_avg", current_avg)
                    historical_std = getattr(self, f"_{operation}_historical_std", current_std)
                    
                    if historical_avg > 0 and current_avg > historical_avg * self.known_patterns["performance_degradation"]["threshold"]:
                        self._create_pattern_alert(
                            "performance_degradation",
                            f"Degradación de performance en operación: {operation}",
                            current_avg / historical_avg,
                            operation
                        )
                    
                    # Actualizar métricas históricas
                    setattr(self, f"_{operation}_historical_avg", 
                           (historical_avg * 0.9) + (current_avg * 0.1))
                    setattr(self, f"_{operation}_historical_std",
                           (historical_std * 0.9) + (current_std * 0.1))
                        
        except Exception as e:
            logger.error(f"Error analizando performance: {str(e)}")
    
    def _analyze_activity_patterns(self):
        """Analizar patrones de actividad y detectar anomalías"""
        try:
            # Analizar distribución de logs por hora
            hourly_activity = defaultdict(int)
            for log in self.log_buffer:
                timestamp = datetime.fromisoformat(log.get("@timestamp", "2000-01-01T00:00:00"))
                hour_key = timestamp.strftime("%H")
                hourly_activity[hour_key] += 1
            
            # Detectar actividad inusual (simplificado)
            if len(hourly_activity.values()) > 0:
                avg_activity = statistics.mean(hourly_activity.values())
                std_activity = statistics.stdev(hourly_activity.values()) if len(hourly_activity.values()) > 1 else 0
                
                current_hour = datetime.now().strftime("%H")
                current_activity = hourly_activity.get(current_hour, 0)
                
                if std_activity > 0 and abs(current_activity - avg_activity) > std_activity * self.known_patterns["unusual_activity"]["threshold"]:
                    self._create_pattern_alert(
                        "unusual_activity",
                        f"Actividad inusual detectada en hora {current_hour}",
                        abs(current_activity - avg_activity) / std_activity,
                        current_hour
                    )
                        
        except Exception as e:
            logger.error(f"Error analizando patrones de actividad: {str(e)}")
    
    def _analyze_security_events(self):
        """Analizar eventos de seguridad y detectar anomalías"""
        try:
            # Obtener eventos de seguridad
            security_logs = [
                log for log in self.log_buffer
                if log.get("operation") == "security_audit"
            ]
            
            if len(security_logs) == 0:
                return
            
            # Contar eventos de seguridad por tipo
            security_by_type = defaultdict(int)
            for log in security_logs:
                event_type = log.get("security_context", {}).get("event_type", "unknown")
                security_by_type[event_type] += 1
            
            # Detectar eventos críticos
            for event_type, count in security_by_type.items():
                if count >= self.known_patterns["security_anomaly"]["threshold"]:
                    self._create_pattern_alert(
                        "security_anomaly",
                        f"Anomalía de seguridad detectada: {event_type}",
                        count,
                        event_type
                    )
                        
        except Exception as e:
            logger.error(f"Error analizando eventos de seguridad: {str(e)}")
    
    def _create_pattern_alert(self, pattern_type: str, description: str, severity_factor: float, affected_operation: str):
        """Crear alerta de patrón detectado"""
        try:
            pattern = LogPattern(
                pattern_id=f"{pattern_type}_{int(time.time())}",
                name=self.known_patterns[pattern_type]["name"],
                description=description,
                severity=self.known_patterns[pattern_type]["severity"],
                frequency=1,
                last_occurrence=datetime.now().isoformat(),
                affected_operations=[affected_operation],
                suggested_actions=self._get_suggested_actions(pattern_type),
                metadata={
                    "severity_factor": severity_factor,
                    "pattern_type": pattern_type,
                    "affected_operation": affected_operation
                }
            )
            
            # Verificar si ya existe un patrón similar
            existing_pattern = next(
                (p for p in self.patterns if p.pattern_id.startswith(pattern_type)),
                None
            )
            
            if existing_pattern:
                existing_pattern.frequency += 1
                existing_pattern.last_occurrence = pattern.last_occurrence
                if affected_operation not in existing_pattern.affected_operations:
                    existing_pattern.affected_operations.append(affected_operation)
            else:
                self.patterns.append(pattern)
                # Enviar alerta
                self._send_pattern_alert(pattern)
                
        except Exception as e:
            logger.error(f"Error creando alerta de patrón: {str(e)}")
    
    def _get_suggested_actions(self, pattern_type: str) -> List[str]:
        """Obtener acciones sugeridas para un tipo de patrón"""
        actions = {
            "high_error_rate": [
                "Verificar estado de servicios dependientes",
                "Revisar logs de error detallados",
                "Validar configuración de rate limiting",
                "Contactar al equipo de soporte"
            ],
            "performance_degradation": [
                "Monitorear métricas de CPU y memoria",
                "Verificar cuellos de botella en base de datos",
                "Revisar configuración de Redis",
                "Optimizar consultas lentas"
            ],
            "unusual_activity": [
                "Verificar si hay mantenimiento programado",
                "Revisar métricas de tráfico",
                "Validar autenticación de usuarios",
                "Monitorear durante el próximo periodo"
            ],
            "security_anomaly": [
                "Bloquear IP sospechosa",
                "Revisar logs de autenticación",
                "Validar permisos de usuario",
                "Notificar al equipo de seguridad"
            ]
        }
        return actions.get(pattern_type, ["Investigar manualmente"])
    
    def _send_pattern_alert(self, pattern: LogPattern):
        """Enviar alerta de patrón detectado"""
        try:
            # Enviar alerta a través del sistema de logging
            alert_data = {
                "operation": "pattern_alert",
                "pattern_type": pattern.pattern_id,
                "severity": pattern.severity,
                "description": pattern.description,
                "affected_operations": pattern.affected_operations,
                "suggested_actions": pattern.suggested_actions,
                "metadata": pattern.metadata
            }
            
            logging_manager.log_event(
                "analytics",
                pattern.severity,
                f"Patrón detectado: {pattern.name}",
                **alert_data
            )
            
        except Exception as e:
            logger.error(f"Error enviando alerta de patrón: {str(e)}")
    
    def _calculate_business_metrics(self):
        """Calcular métricas de negocio a partir de los logs"""
        try:
            # Calcular métricas de mensajes de WhatsApp
            whatsapp_logs = [
                log for log in self.log_buffer
                if log.get("operation") == "whatsapp_message"
            ]
            
            if len(whatsapp_logs) == 0:
                return
            
            # Métricas de mensajes
            total_messages = len(whatsapp_logs)
            sent_messages = sum(1 for log in whatsapp_logs if log.get("status") == "sent")
            failed_messages = sum(1 for log in whatsapp_logs if log.get("status") == "failed")
            delivered_messages = sum(1 for log in whatsapp_logs if log.get("status") == "delivered")
            read_messages = sum(1 for log in whatsapp_logs if log.get("status") == "read")
            
            # Calcular KPIs
            success_rate = sent_messages / total_messages if total_messages > 0 else 0
            delivery_rate = delivered_messages / sent_messages if sent_messages > 0 else 0
            read_rate = read_messages / delivered_messages if delivered_messages > 0 else 0
            
            # Actualizar métricas de negocio
            self.business_metrics.update({
                "whatsapp_total_messages": BusinessMetric(
                    name="Mensajes totales",
                    value=total_messages,
                    unit="messages",
                    trend="stable",
                    timestamp=datetime.now().isoformat(),
                    comparison_period="5m"
                ),
                "whatsapp_success_rate": BusinessMetric(
                    name="Tasa de éxito",
                    value=success_rate * 100,
                    unit="%",
                    trend="stable",
                    timestamp=datetime.now().isoformat(),
                    comparison_period="5m",
                    metadata={"target": 95}
                ),
                "whatsapp_delivery_rate": BusinessMetric(
                    name="Tasa de entrega",
                    value=delivery_rate * 100,
                    unit="%",
                    trend="stable",
                    timestamp=datetime.now().isoformat(),
                    comparison_period="5m",
                    metadata={"target": 90}
                ),
                "whatsapp_read_rate": BusinessMetric(
                    name="Tasa de lectura",
                    value=read_rate * 100,
                    unit="%",
                    trend="stable",
                    timestamp=datetime.now().isoformat(),
                    comparison_period="5m",
                    metadata={"target": 70}
                )
            })
            
        except Exception as e:
            logger.error(f"Error calculando métricas de negocio: {str(e)}")
    
    def get_analytics_dashboard(self) -> Dict[str, Any]:
        """Obtener datos para dashboard de analytics"""
        try:
            return {
                "timestamp": datetime.now().isoformat(),
                "patterns": [
                    {
                        "id": pattern.pattern_id,
                        "name": pattern.name,
                        "severity": pattern.severity,
                        "frequency": pattern.frequency,
                        "last_occurrence": pattern.last_occurrence,
                        "affected_operations": pattern.affected_operations,
                        "description": pattern.description
                    }
                    for pattern in self.patterns[-10:]  # Últimos 10 patrones
                ],
                "business_metrics": {
                    metric_name: {
                        "name": metric.name,
                        "value": metric.value,
                        "unit": metric.unit,
                        "trend": metric.trend,
                        "timestamp": metric.timestamp,
                        "target": metric.metadata.get("target")
                    }
                    for metric_name, metric in self.business_metrics.items()
                },
                "log_statistics": {
                    "total_logs": len(self.log_buffer),
                    "error_logs": len([l for l in self.log_buffer if l.get("level") in ["ERROR", "CRITICAL"]]),
                    "warning_logs": len([l for l in self.log_buffer if l.get("level") == "WARNING"]),
                    "info_logs": len([l for l in self.log_buffer if l.get("level") == "INFO"]),
                    "analysis_window": self.analysis_window
                }
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo dashboard de analytics: {str(e)}")
            return {"error": "Error generando dashboard"}
    
    def get_pattern_trends(self, pattern_type: str = None) -> Dict[str, Any]:
        """Obtener tendencias de patrones"""
        try:
            if pattern_type:
                patterns = [p for p in self.patterns if pattern_type in p.pattern_id]
            else:
                patterns = self.patterns
            
            # Agrupar patrones por tipo y calcular tendencias
            pattern_trends = defaultdict(list)
            for pattern in patterns:
                pattern_trends[pattern.name].append({
                    "timestamp": pattern.last_occurrence,
                    "frequency": pattern.frequency,
                    "severity": pattern.severity
                })
            
            return {
                "pattern_trends": dict(pattern_trends),
                "total_patterns": len(patterns),
                "active_patterns": len([p for p in patterns if p.frequency > 1])
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo tendencias de patrones: {str(e)}")
            return {"error": "Error generando tendencias"}

# Instancia global del motor de analytics
analytics_engine = LogAnalyticsEngine()

def add_log_for_analysis(log_data: Dict[str, Any]):
    """Función de conveniencia para agregar log al análisis"""
    return analytics_engine.add_log_entry(log_data)

def get_analytics_dashboard() -> Dict[str, Any]:
    """Función de conveniencia para obtener dashboard de analytics"""
    return analytics_engine.get_analytics_dashboard()

def get_pattern_trends(pattern_type: str = None) -> Dict[str, Any]:
    """Función de conveniencia para obtener tendencias de patrones"""
    return analytics_engine.get_pattern_trends(pattern_type)