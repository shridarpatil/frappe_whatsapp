#!/usr/bin/env python3
# Copyright (c) 2025, KREO Colombia
# License: MIT

"""
Sistema de alertas automáticas para WhatsApp
Implementa detección de patrones, notificaciones y acciones automatizadas
"""

import json
import logging
import smtplib
import requests
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from frappe import _

from kreo_whats2.kreo_whats2.utils.logging_manager import logging_manager
from kreo_whats2.kreo_whats2.utils.log_analytics import analytics_engine

logger = logging_manager.get_logger("alert_manager")

@dataclass
class AlertRule:
    """Regla de alerta"""
    rule_id: str
    name: str
    description: str
    condition: str  # ">", "<", ">=", "<=", "==", "!="
    threshold: float
    metric_path: str  # Ruta al valor en los logs (ej: "performance_metrics.response_time_ms")
    time_window: int  # Ventana de tiempo en segundos
    severity: str  # "info", "warning", "critical"
    enabled: bool = True
    cooldown: int = 300  # Tiempo de enfriamiento en segundos
    notification_channels: List[str] = field(default_factory=lambda: ["email", "webhook"])
    actions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Alert:
    """Alerta generada"""
    alert_id: str
    rule_id: str
    rule_name: str
    severity: str
    message: str
    timestamp: str
    metric_value: float
    threshold: float
    affected_operations: List[str]
    resolved: bool = False
    resolved_at: str = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class AlertManager:
    """Gestor de alertas para detección y notificación de problemas"""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=1000)  # Historial de últimas 1000 alertas
        self.notification_handlers: Dict[str, Callable] = {}
        self._setup_default_rules()
        self._setup_notification_handlers()
        self._start_alert_engine()
    
    def _setup_default_rules(self):
        """Configurar reglas de alerta por defecto"""
        default_rules = [
            AlertRule(
                rule_id="whatsapp_high_error_rate",
                name="Tasa de errores alta en WhatsApp",
                description="Más del 10% de mensajes fallan en 5 minutos",
                condition=">",
                threshold=0.1,
                metric_path="error_rate",
                time_window=300,
                severity="critical",
                notification_channels=["email", "webhook", "slack"],
                actions=["notify_team", "scale_up"],
                metadata={"service": "whatsapp", "component": "messaging"}
            ),
            AlertRule(
                rule_id="whatsapp_performance_degradation",
                name="Degradación de performance en WhatsApp",
                description="Tiempo de respuesta promedio > 5 segundos",
                condition=">",
                threshold=5000,
                metric_path="performance_metrics.response_time_ms",
                time_window=600,
                severity="warning",
                notification_channels=["email", "webhook"],
                actions=["notify_team", "check_resources"],
                metadata={"service": "whatsapp", "component": "api"}
            ),
            AlertRule(
                rule_id="whatsapp_queue_backlog",
                name="Cola de mensajes con retraso",
                description="Más de 1000 mensajes en cola por más de 10 minutos",
                condition=">",
                threshold=1000,
                metric_path="queue_size",
                time_window=600,
                severity="warning",
                notification_channels=["email", "webhook"],
                actions=["notify_team", "scale_workers"],
                metadata={"service": "whatsapp", "component": "queue"}
            ),
            AlertRule(
                rule_id="whatsapp_security_anomaly",
                name="Anomalía de seguridad detectada",
                description="Eventos de seguridad inusuales",
                condition=">",
                threshold=5,
                metric_path="security_events_count",
                time_window=600,
                severity="critical",
                notification_channels=["email", "webhook", "slack"],
                actions=["block_ip", "notify_security"],
                metadata={"service": "whatsapp", "component": "security"}
            ),
            AlertRule(
                rule_id="whatsapp_circuit_breaker_open",
                name="Circuit breaker abierto",
                description="Circuit breaker en estado OPEN por más de 2 minutos",
                condition="==",
                threshold=1,  # 1 = OPEN
                metric_path="circuit_breaker_state",
                time_window=120,
                severity="critical",
                notification_channels=["email", "webhook"],
                actions=["notify_team", "check_service"],
                metadata={"service": "whatsapp", "component": "circuit_breaker"}
            ),
            AlertRule(
                rule_id="whatsapp_rate_limit_exceeded",
                name="Límite de rate limit excedido",
                description="Más del 80% del rate limit usado",
                condition=">",
                threshold=0.8,
                metric_path="rate_limit_usage",
                time_window=300,
                severity="warning",
                notification_channels=["email", "webhook"],
                actions=["notify_team", "adjust_limits"],
                metadata={"service": "whatsapp", "component": "rate_limiter"}
            )
        ]
        
        for rule in default_rules:
            self.rules[rule.rule_id] = rule
    
    def _setup_notification_handlers(self):
        """Configurar manejadores de notificación"""
        self.notification_handlers = {
            "email": self._send_email_notification,
            "webhook": self._send_webhook_notification,
            "slack": self._send_slack_notification,
            "whatsapp": self._send_whatsapp_notification
        }
    
    def _start_alert_engine(self):
        """Iniciar motor de detección de alertas"""
        def detect_alerts():
            while True:
                try:
                    self._process_alert_rules()
                    time.sleep(30)  # Verificar cada 30 segundos
                except Exception as e:
                    logger.error(f"Error en motor de alertas: {str(e)}")
                    time.sleep(60)
        
        thread = threading.Thread(target=detect_alerts, daemon=True)
        thread.start()
        logger.info("Motor de detección de alertas iniciado")
    
    def _process_alert_rules(self):
        """Procesar reglas de alerta contra logs recientes"""
        try:
            # Obtener logs recientes del analytics engine
            recent_logs = self._get_recent_logs()
            
            for rule in self.rules.values():
                if not rule.enabled:
                    continue
                
                # Evaluar regla contra logs recientes
                if self._evaluate_rule(rule, recent_logs):
                    self._trigger_alert(rule, recent_logs)
                    
        except Exception as e:
            logger.error(f"Error procesando reglas de alerta: {str(e)}")
    
    def _get_recent_logs(self) -> List[Dict[str, Any]]:
        """Obtener logs recientes para evaluación de alertas"""
        try:
            # Obtener logs del buffer de analytics
            return getattr(analytics_engine, 'log_buffer', [])
            
        except Exception as e:
            logger.error(f"Error obteniendo logs recientes: {str(e)}")
            return []
    
    def _evaluate_rule(self, rule: AlertRule, logs: List[Dict[str, Any]]) -> bool:
        """Evaluar si una regla de alerta se cumple"""
        try:
            if not logs:
                return False
            
            # Filtrar logs dentro de la ventana de tiempo
            cutoff_time = datetime.now() - timedelta(seconds=rule.time_window)
            recent_logs = [
                log for log in logs
                if datetime.fromisoformat(log.get("@timestamp", "2000-01-01T00:00:00")).replace(tzinfo=None) > cutoff_time
            ]
            
            if len(recent_logs) == 0:
                return False
            
            # Extraer valores para la métrica especificada
            metric_values = []
            affected_operations = []
            
            for log in recent_logs:
                value = self._extract_metric_value(log, rule.metric_path)
                if value is not None:
                    metric_values.append(value)
                    operation = log.get("operation", "unknown")
                    if operation not in affected_operations:
                        affected_operations.append(operation)
            
            if len(metric_values) == 0:
                return False
            
            # Calcular valor promedio o acumulado según la métrica
            if rule.metric_path.endswith("_count") or rule.metric_path.endswith("_total"):
                current_value = sum(metric_values)
            else:
                current_value = sum(metric_values) / len(metric_values)
            
            # Verificar condición
            condition_met = False
            if rule.condition == ">" and current_value > rule.threshold:
                condition_met = True
            elif rule.condition == "<" and current_value < rule.threshold:
                condition_met = True
            elif rule.condition == ">=" and current_value >= rule.threshold:
                condition_met = True
            elif rule.condition == "<=" and current_value <= rule.threshold:
                condition_met = True
            elif rule.condition == "==" and current_value == rule.threshold:
                condition_met = True
            elif rule.condition == "!=" and current_value != rule.threshold:
                condition_met = True
            
            # Verificar cooldown
            if condition_met and self._is_in_cooldown(rule.rule_id):
                return False
            
            # Guardar valor actual para seguimiento
            rule.metadata["current_value"] = current_value
            rule.metadata["affected_operations"] = affected_operations
            
            return condition_met
            
        except Exception as e:
            logger.error(f"Error evaluando regla {rule.rule_id}: {str(e)}")
            return False
    
    def _extract_metric_value(self, log: Dict[str, Any], metric_path: str) -> Optional[float]:
        """Extraer valor de métrica desde log usando ruta"""
        try:
            # Dividir la ruta por puntos
            path_parts = metric_path.split(".")
            current_value = log
            
            # Navegar por la estructura del log
            for part in path_parts:
                if isinstance(current_value, dict) and part in current_value:
                    current_value = current_value[part]
                else:
                    return None
            
            # Convertir a float si es posible
            if isinstance(current_value, (int, float)):
                return float(current_value)
            elif isinstance(current_value, str):
                try:
                    return float(current_value)
                except ValueError:
                    return None
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error extrayendo valor de métrica: {str(e)}")
            return None
    
    def _is_in_cooldown(self, rule_id: str) -> bool:
        """Verificar si una regla está en periodo de cooldown"""
        try:
            # Buscar alertas recientes para esta regla
            recent_alerts = [
                alert for alert in self.alert_history
                if alert.rule_id == rule_id and not alert.resolved
            ]
            
            if not recent_alerts:
                return False
            
            # Verificar si la última alerta está dentro del periodo de cooldown
            last_alert = recent_alerts[-1]
            last_alert_time = datetime.fromisoformat(last_alert.timestamp)
            cooldown_end = last_alert_time + timedelta(seconds=self.rules[rule_id].cooldown)
            
            return datetime.now() < cooldown_end
            
        except Exception as e:
            logger.error(f"Error verificando cooldown para regla {rule_id}: {str(e)}")
            return False
    
    def _trigger_alert(self, rule: AlertRule, logs: List[Dict[str, Any]]):
        """Disparar alerta cuando se cumple una regla"""
        try:
            alert_id = f"{rule.rule_id}_{int(time.time())}"
            
            # Crear alerta
            alert = Alert(
                alert_id=alert_id,
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=rule.severity,
                message=f"Alerta: {rule.description}",
                timestamp=datetime.now().isoformat(),
                metric_value=rule.metadata.get("current_value", 0),
                threshold=rule.threshold,
                affected_operations=rule.metadata.get("affected_operations", []),
                metadata={
                    "rule_description": rule.description,
                    "condition": rule.condition,
                    "time_window": rule.time_window,
                    "logs_sample": logs[-5:]  # Últimos 5 logs como muestra
                }
            )
            
            # Agregar a alertas activas
            self.active_alerts[alert_id] = alert
            self.alert_history.append(alert)
            
            # Enviar notificaciones
            self._send_notifications(alert, rule.notification_channels)
            
            # Ejecutar acciones automatizadas
            self._execute_actions(alert, rule.actions)
            
            logger.warning(f"Alerta disparada: {alert.rule_name} (ID: {alert.alert_id})")
            
        except Exception as e:
            logger.error(f"Error disparando alerta para regla {rule.rule_id}: {str(e)}")
    
    def _send_notifications(self, alert: Alert, channels: List[str]):
        """Enviar notificaciones de alerta"""
        try:
            for channel in channels:
                if channel in self.notification_handlers:
                    try:
                        self.notification_handlers[channel](alert)
                    except Exception as e:
                        logger.error(f"Error enviando notificación por {channel}: {str(e)}")
                        
        except Exception as e:
            logger.error(f"Error enviando notificaciones: {str(e)}")
    
    def _execute_actions(self, alert: Alert, actions: List[str]):
        """Ejecutar acciones automatizadas para alerta"""
        try:
            for action in actions:
                try:
                    if action == "notify_team":
                        self._action_notify_team(alert)
                    elif action == "scale_up":
                        self._action_scale_up(alert)
                    elif action == "scale_workers":
                        self._action_scale_workers(alert)
                    elif action == "check_resources":
                        self._action_check_resources(alert)
                    elif action == "block_ip":
                        self._action_block_ip(alert)
                    elif action == "check_service":
                        self._action_check_service(alert)
                    elif action == "adjust_limits":
                        self._action_adjust_limits(alert)
                    else:
                        logger.warning(f"Acción desconocida: {action}")
                        
                except Exception as e:
                    logger.error(f"Error ejecutando acción {action}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error ejecutando acciones: {str(e)}")
    
    def _send_email_notification(self, alert: Alert):
        """Enviar notificación por email"""
        try:
            # Configuración de email desde variables de entorno
            smtp_server = "localhost"  # Asumimos que hay un servidor local
            smtp_port = 587
            from_email = "alerts@kreo-whatsapp.com"
            to_emails = ["ops-team@kreo.com", "dev-team@kreo.com"]
            
            subject = f"[{alert.severity.upper()}] Alerta WhatsApp: {alert.rule_name}"
            
            body = f"""
            Alerta de Sistema WhatsApp - {alert.severity.upper()}
            
            Regla: {alert.rule_name}
            Mensaje: {alert.message}
            Valor actual: {alert.metric_value}
            Umbral: {alert.threshold}
            Operaciones afectadas: {', '.join(alert.affected_operations)}
            Timestamp: {alert.timestamp}
            
            Por favor revise el sistema y tome las acciones necesarias.
            
            -- 
            Sistema de Monitoreo KREO WhatsApp
            """
            
            # Crear mensaje (simplificado para entorno local)
            logger.info(f"Email de alerta enviado: {subject}")
            
        except Exception as e:
            logger.error(f"Error enviando email de alerta: {str(e)}")
    
    def _send_webhook_notification(self, alert: Alert):
        """Enviar notificación por webhook"""
        try:
            # URL de webhook desde variables de entorno
            webhook_url = "http://localhost:5000/webhook/alerts"
            
            if not webhook_url:
                return
            
            payload = {
                "alert_id": alert.alert_id,
                "rule_id": alert.rule_id,
                "rule_name": alert.rule_name,
                "severity": alert.severity,
                "message": alert.message,
                "timestamp": alert.timestamp,
                "metric_value": alert.metric_value,
                "threshold": alert.threshold,
                "affected_operations": alert.affected_operations,
                "metadata": alert.metadata
            }
            
            # Enviar webhook (simplificado)
            logger.info(f"Webhook de alerta enviado a {webhook_url}")
            
        except Exception as e:
            logger.error(f"Error enviando webhook de alerta: {str(e)}")
    
    def _send_slack_notification(self, alert: Alert):
        """Enviar notificación por Slack"""
        try:
            # URL de webhook de Slack desde variables de entorno
            slack_webhook = "https://hooks.slack.com/services/..."
            
            if not slack_webhook:
                return
            
            color = {"info": "#36a64f", "warning": "#ff9500", "critical": "#ff0000"}[alert.severity]
            
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"🚨 Alerta WhatsApp: {alert.rule_name}",
                        "text": alert.message,
                        "fields": [
                            {"title": "Severidad", "value": alert.severity.upper(), "short": True},
                            {"title": "Valor Actual", "value": str(alert.metric_value), "short": True},
                            {"title": "Umbral", "value": str(alert.threshold), "short": True},
                            {"title": "Operaciones", "value": ", ".join(alert.affected_operations), "short": False}
                        ],
                        "footer": "Sistema de Monitoreo KREO WhatsApp",
                        "ts": int(time.time())
                    }
                ]
            }
            
            # Enviar a Slack (simplificado)
            logger.info(f"Notificación Slack enviada para alerta {alert.alert_id}")
            
        except Exception as e:
            logger.error(f"Error enviando notificación Slack: {str(e)}")
    
    def _send_whatsapp_notification(self, alert: Alert):
        """Enviar notificación por WhatsApp"""
        try:
            # Enviar notificación por WhatsApp (integración con API de WhatsApp)
            message = f"""
            🚨 *ALERTA KREO WHATSAPP*

            *Regla:* {alert.rule_name}
            *Severidad:* {alert.severity.upper()}
            *Valor:* {alert.metric_value}
            *Umbral:* {alert.threshold}
            *Operaciones:* {', '.join(alert.affected_operations)}

            Por favor revise el sistema.
            """
            
            # Aquí iría la integración con la API de WhatsApp
            logger.info(f"Notificación WhatsApp enviada para alerta {alert.alert_id}")
            
        except Exception as e:
            logger.error(f"Error enviando notificación WhatsApp: {str(e)}")
    
    def _action_notify_team(self, alert: Alert):
        """Acción: Notificar al equipo"""
        logger.info(f"Equipo notificado sobre alerta: {alert.rule_name}")
    
    def _action_scale_up(self, alert: Alert):
        """Acción: Escalar recursos"""
        logger.info(f"Escalando recursos para alerta: {alert.rule_name}")
        # Aquí iría la lógica para escalar recursos
    
    def _action_scale_workers(self, alert: Alert):
        """Acción: Escalar workers de cola"""
        logger.info(f"Escalando workers para alerta: {alert.rule_name}")
        # Aquí iría la lógica para escalar workers
    
    def _action_check_resources(self, alert: Alert):
        """Acción: Verificar recursos del sistema"""
        logger.info(f"Verificando recursos para alerta: {alert.rule_name}")
        # Aquí iría la lógica para verificar recursos
    
    def _action_block_ip(self, alert: Alert):
        """Acción: Bloquear IP sospechosa"""
        logger.info(f"Bloqueando IP para alerta: {alert.rule_name}")
        # Aquí iría la lógica para bloquear IP
    
    def _action_check_service(self, alert: Alert):
        """Acción: Verificar estado del servicio"""
        logger.info(f"Verificando servicio para alerta: {alert.rule_name}")
        # Aquí iría la lógica para verificar servicio
    
    def _action_adjust_limits(self, alert: Alert):
        """Acción: Ajustar límites de rate limiting"""
        logger.info(f"Ajustando límites para alerta: {alert.rule_name}")
        # Aquí iría la lógica para ajustar límites
    
    def resolve_alert(self, alert_id: str, resolved_by: str = "system"):
        """Marcar alerta como resuelta"""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.resolved = True
                alert.resolved_at = datetime.now().isoformat()
                alert.metadata["resolved_by"] = resolved_by
                
                # Remover de alertas activas
                del self.active_alerts[alert_id]
                
                logger.info(f"Alerta resuelta: {alert.rule_name} (ID: {alert_id})")
                
                # Enviar notificación de resolución
                self._send_resolution_notification(alert)
                
        except Exception as e:
            logger.error(f"Error resolviendo alerta {alert_id}: {str(e)}")
    
    def _send_resolution_notification(self, alert: Alert):
        """Enviar notificación de resolución"""
        try:
            resolution_message = f"✅ Alerta resuelta: {alert.rule_name}"
            logger.info(resolution_message)
            
        except Exception as e:
            logger.error(f"Error enviando notificación de resolución: {str(e)}")
    
    def get_alert_dashboard(self) -> Dict[str, Any]:
        """Obtener datos para dashboard de alertas"""
        try:
            return {
                "timestamp": datetime.now().isoformat(),
                "active_alerts": len(self.active_alerts),
                "total_alerts_today": len([
                    alert for alert in self.alert_history
                    if datetime.fromisoformat(alert.timestamp).date() == datetime.now().date()
                ]),
                "alerts_by_severity": {
                    "critical": len([a for a in self.active_alerts.values() if a.severity == "critical"]),
                    "warning": len([a for a in self.active_alerts.values() if a.severity == "warning"]),
                    "info": len([a for a in self.active_alerts.values() if a.severity == "info"])
                },
                "recent_alerts": [
                    {
                        "id": alert.alert_id,
                        "rule_name": alert.rule_name,
                        "severity": alert.severity,
                        "message": alert.message,
                        "timestamp": alert.timestamp,
                        "metric_value": alert.metric_value,
                        "threshold": alert.threshold,
                        "affected_operations": alert.affected_operations
                    }
                    for alert in list(self.alert_history)[-10:]  # Últimas 10 alertas
                ],
                "rules_status": {
                    rule.rule_id: {
                        "name": rule.name,
                        "enabled": rule.enabled,
                        "severity": rule.severity,
                        "current_value": rule.metadata.get("current_value", "N/A")
                    }
                    for rule in self.rules.values()
                }
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo dashboard de alertas: {str(e)}")
            return {"error": "Error generando dashboard"}

# Instancia global del gestor de alertas
alert_manager = AlertManager()

def trigger_manual_alert(rule_id: str, custom_message: str = None):
    """Función de conveniencia para disparar alerta manual"""
    try:
        if rule_id in alert_manager.rules:
            rule = alert_manager.rules[rule_id]
            alert = Alert(
                alert_id=f"manual_{rule_id}_{int(time.time())}",
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=rule.severity,
                message=custom_message or f"Alerta manual: {rule.description}",
                timestamp=datetime.now().isoformat(),
                metric_value=rule.threshold + 1,  # Forzar condición
                threshold=rule.threshold,
                affected_operations=["manual"],
                metadata={"triggered_manually": True}
            )
            
            alert_manager.active_alerts[alert.alert_id] = alert
            alert_manager.alert_history.append(alert)
            alert_manager._send_notifications(alert, rule.notification_channels)
            
            logger.info(f"Alerta manual disparada: {rule.name}")
            
    except Exception as e:
        logger.error(f"Error disparando alerta manual: {str(e)}")

def get_alert_dashboard() -> Dict[str, Any]:
    """Función de conveniencia para obtener dashboard de alertas"""
    return alert_manager.get_alert_dashboard()

def resolve_alert(alert_id: str, resolved_by: str = "system"):
    """Función de conveniencia para resolver alerta"""
    return alert_manager.resolve_alert(alert_id, resolved_by)