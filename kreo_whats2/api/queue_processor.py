# Copyright (c) 2025, KREO Colombia
# License: MIT

import frappe
from frappe import _
import json
import redis
import logging
import time
from datetime import datetime
from kreo_whats2.kreo_whats2.api.whatsapp_api import whatsapp_api

# Configuración de logging
logger = logging.getLogger(__name__)

# Importar logging avanzado
try:
    from kreo_whats2.kreo_whats2.utils.logging_manager import (
        logging_manager, log_event, log_error,
        log_performance, log_whatsapp_event,
        handle_whatsapp_errors, get_logger
    )
    ADVANCED_LOGGING_AVAILABLE = True
    logger = get_logger("queue_processor")
except ImportError:
    ADVANCED_LOGGING_AVAILABLE = False
    print("Advertencia: Logging avanzado no disponible")

class QueueProcessor:
    """Procesador de colas Redis para mensajes WhatsApp"""
    
    def __init__(self):
        self.redis_client = None
        self._connect_redis()
        self._setup_logging()
    
    @log_whatsapp_event("connect_redis")
    @handle_whatsapp_errors("queue_processor")
    def _connect_redis(self):
        """Conectar a Redis"""
        start_time = time.time()
        correlation_id = None
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "connect_redis",
                    component="queue_processor",
                    metadata={
                        "operation": "_connect_redis"
                    }
                )
            
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            self.redis_client = redis.from_url(
                whatsapp_settings.redis_queue_url or "redis://redis-queue:6379/1"
            )
            self.redis_client.ping()
            
            # Calcular tiempo de respuesta
            response_time = (time.time() - start_time) * 1000
            
            logger.info("Conectado a Redis Queue exitosamente")
            
            # Registrar conexión exitosa con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("queue_processor", "redis_connected", {
                    "status": "success"
                }, performance_metrics={
                    "response_time_ms": response_time
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "success",
                    business_metrics={
                        "redis_connections": 1
                    }
                )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("queue_processor", e, {
                    "operation": "_connect_redis",
                    "correlation_id": correlation_id
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "connection_error",
                            "error_message": str(e)
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            
            logger.error(f"Error conectando a Redis: {str(e)}")
            self.redis_client = None
    
    def _setup_logging(self):
        """Configurar logging"""
        try:
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            
            if whatsapp_settings.enable_detailed_logging:
                log_level = getattr(logging, whatsapp_settings.log_level.upper(), logging.INFO)
                logger.setLevel(log_level)
                
                # Configurar handler para archivo
                log_file = f"{whatsapp_settings.log_file_path or 'logs/whatsapp'}/queue_processor.log"
                
                # Crear directorio si no existe
                import os
                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                
                # Configurar file handler
                file_handler = logging.FileHandler(log_file)
                file_handler.setLevel(log_level)
                
                # Configurar formatter
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                file_handler.setFormatter(formatter)
                
                # Agregar handler al logger
                logger.addHandler(file_handler)
                
                logger.info(f"Logging Queue Processor configurado en nivel {log_level} hacia {log_file}")
            
        except Exception as e:
            logger.error(f"Error configurando logging: {str(e)}")
    
    @log_whatsapp_event("process_queue")
    @handle_whatsapp_errors("queue_processor")
    def process_queue(self, batch_size=10):
        """Procesar cola de mensajes WhatsApp"""
        if not self.redis_client:
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("queue_processor", "redis_client_unavailable", {
                    "status": "error",
                    "error_type": "connection_error"
                })
            logger.error("Cliente Redis no disponible")
            return {"success": False, "error": "Cliente Redis no disponible"}
        
        start_time = time.time()
        correlation_id = None
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "process_queue",
                    batch_size=batch_size,
                    metadata={
                        "component": "queue_processor",
                        "operation_type": "batch_processing"
                    }
                )
            
            # Obtener configuración
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            queue_name = whatsapp_settings.redis_queue_name or "kreo_whatsapp_queue"
            
            processed_count = 0
            failed_count = 0
            
            logger.info(f"Iniciando procesamiento de cola {queue_name}")
            
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("queue_processor", "queue_processing_started", {
                    "queue_name": queue_name,
                    "batch_size": batch_size,
                    "correlation_id": correlation_id
                })
            
            # Procesar mensajes en lote
            while True:
                # Obtener mensajes de la cola
                messages = self.redis_client.lrange(queue_name, 0, batch_size - 1)
                
                if not messages:
                    # No hay más mensajes
                    break
                
                # Procesar cada mensaje
                for message_data in messages:
                    try:
                        message_dict = json.loads(message_data)
                        result = self._process_message(message_dict)
                        
                        if result.get("success"):
                            processed_count += 1
                            logger.info(f"Mensaje {message_dict.get('message_id')} procesado exitosamente")
                        else:
                            failed_count += 1
                            logger.error(f"Error procesando mensaje {message_dict.get('message_id')}: {result.get('error')}")
                            
                            # Reintentar si aplica
                            if message_dict.get('retry_count', 0) < message_dict.get('max_retries', 3):
                                self._retry_message(message_dict)
                    
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"Error procesando mensaje: {str(e)}")
                
                # Eliminar mensajes procesados de la cola
                self.redis_client.ltrim(queue_name, batch_size, -1)
                
                # Pequeña pausa para no sobrecargar
                time.sleep(0.1)
                
                # Verificar si debemos continuar
                queue_size = self.redis_client.llen(queue_name)
                if queue_size == 0:
                    break
            
            # Estadísticas finales
            total_processed = processed_count + failed_count
            success_rate = (processed_count / total_processed * 100) if total_processed > 0 else 0
            total_time = (time.time() - start_time) * 1000
            
            logger.info(f"Procesamiento completado: {processed_count} exitosos, {failed_count} fallidos, {success_rate:.1f}% éxito")
            
            # Registrar métricas con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("queue_processor", "queue_processing_completed", {
                    "queue_name": queue_name,
                    "processed_count": processed_count,
                    "failed_count": failed_count,
                    "success_rate": success_rate,
                    "batch_size": batch_size
                }, performance_metrics={
                    "total_time_ms": total_time,
                    "avg_time_per_message": total_time / total_processed if total_processed > 0 else 0
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "success",
                    business_metrics={
                        "messages_processed": processed_count,
                        "messages_failed": failed_count,
                        "success_rate": success_rate / 100
                    },
                    performance_metrics={
                        "total_time_ms": total_time,
                        "avg_time_per_message": total_time / total_processed if total_processed > 0 else 0
                    }
                )
            
            return {
                "success": True,
                "processed": processed_count,
                "failed": failed_count,
                "success_rate": success_rate
            }
            
        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("queue_processor", e, {
                    "operation": "process_queue",
                    "batch_size": batch_size,
                    "queue_name": queue_name if 'queue_name' in locals() else "unknown",
                    "correlation_id": correlation_id
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "exception",
                            "error_message": str(e)
                        },
                        performance_metrics={
                            "total_time_ms": total_time
                        }
                    )
            
            logger.error(f"Error procesando cola: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @log_whatsapp_event("process_message")
    @handle_whatsapp_errors("queue_processor")
    def _process_message(self, message_dict):
        """Procesar mensaje individual"""
        start_time = time.time()
        correlation_id = None
        message_id = message_dict.get("message_id")
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "process_message",
                    message_id=message_id,
                    recipient=message_dict.get("recipient_phone"),
                    template=message_dict.get("template_name"),
                    metadata={
                        "operation": "_process_message",
                        "message_type": "template" if message_dict.get("template_name") else "custom"
                    }
                )
            
            recipient_phone = message_dict.get("recipient_phone")
            content = message_dict.get("content")
            template_name = message_dict.get("template_name")
            template_data = json.loads(message_dict.get("template_data", "{}"))
            
            # Enviar mensaje según tipo
            if template_name:
                result = whatsapp_api.send_template_message(
                    recipient_phone, template_name, template_data
                )
            else:
                result = whatsapp_api.send_custom_message(recipient_phone, content)
            
            # Calcular tiempo de respuesta
            response_time = (time.time() - start_time) * 1000
            
            # Actualizar estado del mensaje
            if result.get("success"):
                from kreo_whats2.kreo_whats2.doctype.whatsapp_message.whatsapp_message import WhatsAppMessage
                
                WhatsAppMessage.update_delivery_status(
                    message_id, "Sent", result.get("message_id")
                )
                
                # Registrar mensaje procesado exitosamente con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_event("queue_processor", "message_processed_success", {
                        "message_id": message_id,
                        "recipient_phone": recipient_phone,
                        "template_name": template_name,
                        "message_type": "template" if template_name else "custom"
                    }, performance_metrics={
                        "response_time_ms": response_time
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "success",
                        business_metrics={
                            "messages_processed": 1,
                            "message_type": "template" if template_name else "custom"
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            else:
                # Incrementar contador de reintento
                retry_count = message_dict.get("retry_count", 0) + 1
                message_dict["retry_count"] = retry_count
                
                # Registrar error con logging avanzado
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_event("queue_processor", "message_processing_failed", {
                        "message_id": message_id,
                        "recipient_phone": recipient_phone,
                        "template_name": template_name,
                        "error_message": result.get("error"),
                        "retry_count": retry_count
                    }, performance_metrics={
                        "response_time_ms": response_time
                    })
                    
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "processing_error",
                            "error_message": result.get("error"),
                            "retry_count": retry_count
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
                
                # Reencolar para reintento
                if retry_count <= message_dict.get("max_retries", 3):
                    self._requeue_message(message_dict)
                else:
                    # Marcar como fallido permanentemente
                    self._mark_message_failed(message_id, result.get("error"))
            
            return result
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            # Registrar excepción con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("queue_processor", e, {
                    "operation": "_process_message",
                    "message_id": message_id,
                    "correlation_id": correlation_id
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "exception",
                            "error_message": str(e)
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            
            logger.error(f"Error procesando mensaje {message_id}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _retry_message(self, message_dict):
        """Reencolar mensaje para reintento"""
        try:
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            queue_name = whatsapp_settings.redis_queue_name or "kreo_whatsapp_queue"
            
            # Esperar antes de reintentar
            retry_interval = message_dict.get("retry_interval", 300)
            time.sleep(retry_interval)
            
            # Reencolar mensaje
            self.redis_client.lpush(queue_name, json.dumps(message_dict))
            
            logger.info(f"Mensaje {message_dict.get('message_id')} reencolado para reintento")
            
        except Exception as e:
            logger.error(f"Error reencolando mensaje: {str(e)}")
    
    def _mark_message_failed(self, message_id, error_message):
        """Marcar mensaje como fallido permanentemente"""
        try:
            from kreo_whats2.kreo_whats2.doctype.whatsapp_message.whatsapp_message import WhatsAppMessage
            
            WhatsAppMessage.update_delivery_status(
                message_id, "Failed", None, error_message
            )
            
            logger.error(f"Mensaje {message_id} marcado como fallido: {error_message}")
            
        except Exception as e:
            logger.error(f"Error marcando mensaje como fallido: {str(e)}")
    
    @log_whatsapp_event("get_queue_status")
    @handle_whatsapp_errors("queue_processor")
    def get_queue_status(self):
        """Obtener estado actual de la cola"""
        start_time = time.time()
        correlation_id = None
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "get_queue_status",
                    metadata={
                        "operation": "get_queue_status"
                    }
                )
            
            if not self.redis_client:
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_event("queue_processor", "redis_client_unavailable", {
                        "status": "error",
                        "error_type": "connection_error"
                    })
                return {"error": "Cliente Redis no disponible"}
            
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            queue_name = whatsapp_settings.redis_queue_name or "kreo_whatsapp_queue"
            
            queue_size = self.redis_client.llen(queue_name)
            
            # Obtener estadísticas del día
            today = datetime.now().strftime('%Y-%m-%d')
            stats_key = f"whatsapp_queue_stats:{today}"
            stats = self.redis_client.hgetall(stats_key)
            
            processed_today = 0
            failed_today = 0
            
            if stats:
                stats_dict = {k.decode(): v.decode() for k, v in stats.items()}
                processed_today = int(stats_dict.get("processed", 0))
                failed_today = int(stats_dict.get("failed", 0))
            
            # Calcular tiempo de respuesta
            response_time = (time.time() - start_time) * 1000
            
            result = {
                "queue_size": queue_size,
                "processed_today": processed_today,
                "failed_today": failed_today,
                "success_rate": (processed_today / (processed_today + failed_today) * 100) if (processed_today + failed_today) > 0 else 0
            }
            
            # Registrar operación exitosa con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("queue_processor", "queue_status_retrieved", {
                    "queue_name": queue_name,
                    "queue_size": queue_size,
                    "processed_today": processed_today,
                    "failed_today": failed_today,
                    "success_rate": result["success_rate"]
                }, performance_metrics={
                    "response_time_ms": response_time
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "success",
                    business_metrics={
                        "queue_size": queue_size,
                        "processed_today": processed_today,
                        "failed_today": failed_today
                    },
                    performance_metrics={
                        "response_time_ms": response_time
                    }
                )
            
            return result
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("queue_processor", e, {
                    "operation": "get_queue_status",
                    "correlation_id": correlation_id
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "exception",
                            "error_message": str(e)
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            
            logger.error(f"Error obteniendo estado de cola: {str(e)}")
            return {"error": str(e)}
    
    @log_whatsapp_event("clear_queue")
    @handle_whatsapp_errors("queue_processor")
    def clear_queue(self):
        """Limpiar cola de mensajes"""
        start_time = time.time()
        correlation_id = None
        
        try:
            # Iniciar contexto de operación si está disponible el logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                correlation_id = logging_manager.start_operation_context(
                    "clear_queue",
                    metadata={
                        "operation": "clear_queue"
                    }
                )
            
            if not self.redis_client:
                if ADVANCED_LOGGING_AVAILABLE:
                    logging_manager.log_event("queue_processor", "redis_client_unavailable", {
                        "status": "error",
                        "error_type": "connection_error"
                    })
                return {"error": "Cliente Redis no disponible"}
            
            whatsapp_settings = frappe.get_single("WhatsApp Settings")
            queue_name = whatsapp_settings.redis_queue_name or "kreo_whatsapp_queue"
            
            # Eliminar todos los mensajes
            cleared_count = self.redis_client.delete(queue_name)
            
            # Calcular tiempo de respuesta
            response_time = (time.time() - start_time) * 1000
            
            logger.info(f"Cola {queue_name} limpiada: {cleared_count} mensajes eliminados")
            
            # Registrar operación exitosa con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_event("queue_processor", "queue_cleared", {
                    "queue_name": queue_name,
                    "cleared_count": cleared_count,
                    "status": "success"
                }, performance_metrics={
                    "response_time_ms": response_time
                })
                
                logging_manager.end_operation_context(
                    correlation_id, "success",
                    business_metrics={
                        "messages_cleared": cleared_count
                    },
                    performance_metrics={
                        "response_time_ms": response_time
                    }
                )
            
            return {
                "success": True,
                "cleared_count": cleared_count
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            # Registrar error con logging avanzado
            if ADVANCED_LOGGING_AVAILABLE:
                logging_manager.log_error("queue_processor", e, {
                    "operation": "clear_queue",
                    "correlation_id": correlation_id
                })
                
                if correlation_id:
                    logging_manager.end_operation_context(
                        correlation_id, "error",
                        error_details={
                            "error_type": "exception",
                            "error_message": str(e)
                        },
                        performance_metrics={
                            "response_time_ms": response_time
                        }
                    )
            
            logger.error(f"Error limpiando cola: {str(e)}")
            return {"success": False, "error": str(e)}

# Instancia global del procesador
queue_processor = QueueProcessor()