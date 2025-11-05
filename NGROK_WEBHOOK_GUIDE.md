# Guía de Configuración de Webhooks con Ngrok para KREO WhatsApp

## 📋 Resumen

Esta guía describe cómo configurar y usar el sistema de webhooks con Ngrok para desarrollo local en KREO WhatsApp. El sistema permite a los desarrolladores probar la integración de WhatsApp en entornos locales usando túneles Ngrok.

## 🎯 Funcionalidades Implementadas

### 1. Comandos CLI para Ngrok
- `bench ngrok start` - Iniciar túnel Ngrok
- `bench ngrok stop` - Detener túnel Ngrok
- `bench ngrok status` - Ver estado del túnel
- `bench ngrok configure` - Configurar authtoken y subdominio
- `bench ngrok restart` - Reiniciar túnel
- `bench ngrok logs` - Mostrar logs de Ngrok

### 2. Gestión de Webhooks
- Registro automático de webhooks con Meta API
- Validación de callbacks de Meta
- Manejo de eventos de webhook (mensajes, entregas, errores)
- Integración con la API de WhatsApp existente

### 3. Configuración Avanzada de Ngrok
- Soporte para authtoken personalizado
- Subdominio personalizado
- Puerto configurable (default: 8000)
- Protocolo HTTPS obligatorio
- Manejo de errores de conexión

### 4. Integración con Frappe
- Almacenamiento de configuración en WhatsApp Settings
- Logs detallados en el sistema
- Verificación de estado en health checks
- Compatibilidad con Redis Queue

## 🚀 Configuración Inicial

### Requisitos Previos

1. **Instalar pyngrok** (opcional pero recomendado):
   ```bash
   pip install pyngrok
   ```

2. **Obtener authtoken de Ngrok**:
   - Registrarse en [ngrok.com](https://ngrok.com)
   - Obtener el authtoken desde el dashboard
   - Configurarlo con: `bench ngrok configure --authtoken <tu_token>`

### Configuración Básica

1. **Configurar WhatsApp Settings**:
   - Acceder a `WhatsApp Settings` en Frappe
   - Habilitar WhatsApp
   - Configurar credenciales de Meta Business API
   - Configurar Ngrok authtoken y subdominio

2. **Iniciar Ngrok**:
   ```bash
   bench ngrok start --port 8000 --subdomain tu-subdominio
   ```

3. **Registrar Webhook**:
   ```bash
   bench ngrok start --port 8000 --subdomain tu-subdominio
   # El webhook se registra automáticamente si auto_register_webhook está habilitado
   ```

## 📖 Uso de Comandos CLI

### Iniciar Ngrok
```bash
# Iniciar con configuración por defecto (puerto 8000)
bench ngrok start

# Iniciar con puerto personalizado
bench ngrok start --port 3000

# Iniciar con subdominio personalizado
bench ngrok start --subdomain mi-subdominio

# Iniciar con authtoken temporal
bench ngrok start --authtoken tu-token-temporal
```

### Detener Ngrok
```bash
bench ngrok stop
```

### Ver Estado
```bash
bench ngrok status
```

### Configurar Credenciales
```bash
# Configurar authtoken y subdominio
bench ngrok configure --authtoken tu-token --subdomain tu-subdominio

# Solo configurar authtoken
bench ngrok configure --authtoken tu-token
```

### Reiniciar Ngrok
```bash
bench ngrok restart --port 8000
```

### Ver Logs
```bash
# Mostrar últimos 50 líneas de logs
bench ngrok logs

# Seguir logs en tiempo real
bench ngrok logs --follow

# Mostrar últimas 100 líneas
bench ngrok logs --lines 100
```

## 🔧 Configuración en WhatsApp Settings

### Campos Agregados

1. **Ngrok Authtoken**: Token de autenticación para Ngrok
2. **Subdominio Ngrok**: Subdominio personalizado para el túnel
3. **Registrar Webhook Automáticamente**: Habilitar registro automático
4. **Webhook Registrado**: Indicador de estado (solo lectura)
5. **Fecha de Registro del Webhook**: Timestamp del registro (solo lectura)

### Botones de Acción

1. **Probar Conexión Ngrok**: Verificar conexión del túnel
2. **Obtener Estado Ngrok**: Mostrar información detallada del túnel
3. **Registrar Webhook Automáticamente**: Registrar webhook manualmente

## 📊 Monitoreo y Health Checks

### Verificación de Salud
El sistema incluye un health check completo que verifica:

- Conexión con Meta API
- Conexión Redis
- Estado del túnel Ngrok
- Registro de webhook

```python
# Desde WhatsApp Settings
whatsapp_settings.health_check()
```

### Métricas Disponibles

- **Rate Limiting Status**: Uso actual de límites de tasa
- **Ngrok Connection Test**: Prueba de conectividad del túnel
- **Webhook Status**: Estado del webhook registrado

## 🔍 Pruebas de Integración

### Ejecutar Pruebas
```bash
cd apps/kreo_whats2
python -m pytest tests/test_ngrok_webhook_integration.py -v
```

### Pruebas Incluidas

1. **Inicialización de componentes**
2. **Gestión de túneles Ngrok**
3. **Registro y verificación de webhooks**
4. **Procesamiento de eventos**
5. **Manejo de errores**
6. **Integración con logging**
7. **Health checks**

## 📝 Logging y Depuración

### Niveles de Logging
- DEBUG: Información detallada para desarrollo
- INFO: Eventos generales del sistema
- WARNING: Advertencias y condiciones inusuales
- ERROR: Errores que no detienen el sistema
- CRITICAL: Errores graves que requieren atención

### Archivos de Log
- `logs/whatsapp/whatsapp.log`: Log general del sistema
- `logs/whatsapp/ngrok_manager.log`: Logs específicos de Ngrok
- `logs/whatsapp/webhook_config.log`: Logs de configuración de webhooks

### Decoradores de Logging
```python
from kreo_whats2.kreo_whats2.utils.logging_manager import log_whatsapp_event, handle_whatsapp_errors

@log_whatsapp_event(level="INFO", module="my_module")
def my_function():
    pass

@handle_whatsapp_errors(module="my_module")
def my_function_with_error_handling():
    pass
```

## 🔒 Seguridad

### Validación de Webhooks
- Verificación de tokens de autenticación
- Validación de formato de mensajes
- Control de acceso HTTPS
- Validación de origen (Meta API)

### Rate Limiting
- Límite configurable de mensajes por segundo
- Control de concurrencia
- Cola de mensajes con tamaño máximo
- Integración con Redis

## 🛠️ Solución de Problemas

### Problemas Comunes

1. **Ngrok no se inicia**
   - Verificar que ngrok esté instalado: `ngrok --version`
   - Comprobar authtoken: `bench ngrok configure`
   - Revisar logs: `bench ngrok logs`

2. **Webhook no se registra**
   - Verificar credenciales de Meta API
   - Comprobar conexión Ngrok: `bench ngrok test_connection`
   - Revisar logs de webhook

3. **Eventos no se procesan**
   - Verificar health check
   - Revisar cola de Redis
   - Comprobar logs de procesamiento

### Comandos de Depuración
```bash
# Verificar estado del sistema
bench execute "frappe.get_single('WhatsApp Settings').health_check()"

# Probar conexión Ngrok
bench execute "frappe.get_single('WhatsApp Settings').test_ngrok_connection()"

# Ver estado de rate limiting
bench execute "frappe.get_single('WhatsApp Settings').get_rate_limit_status()"
```

## 📈 Mejores Prácticas

1. **Uso de pyngrok**: Preferir pyngrok sobre subprocess para mejor control
2. **Subdominios personalizados**: Usar subdominios memorables para desarrollo
3. **Logging detallado**: Habilitar logging en entornos de desarrollo
4. **Health checks regulares**: Monitorear el estado del sistema
5. **Pruebas automatizadas**: Ejecutar pruebas de integración regularmente

## 📚 Recursos Adicionales

- [Documentación de Ngrok](https://ngrok.com/docs)
- [Documentación de WhatsApp Business API](https://developers.facebook.com/docs/whatsapp)
- [Guía de Frappe CLI](https://frappeframework.com/docs/user/en/bench)
- [Documentación de Redis](https://redis.io/documentation)

## 🤝 Soporte

Para soporte técnico o reportar problemas:

1. Revisar los logs del sistema
2. Ejecutar pruebas de integración
3. Verificar health checks
4. Consultar esta documentación
5. Contactar al equipo de desarrollo

---

*Última actualización: 2025-10-27*
*Versión del sistema: FASE 4 Optimizada*