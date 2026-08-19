# Hoja de ruta

## Fase 1 — Fundamentos

- API de expedientes, relaciones y tareas.
- Cómputo provisional de términos con explicación.
- Pruebas y CI.
- Modelo de amenazas y límites de uso.

## Fase 2 — Persistencia y acceso

- [x] SQLite para desarrollo y PostgreSQL mediante Docker.
- [x] Contexto obligatorio de bufete.
- [x] Registro inicial de auditoría.
- [x] Migraciones versionadas.
- [x] Usuarios, tokens hash y roles básicos.
- [ ] Autenticación multifactor, recuperación y rotación de credenciales.
- [ ] Bitácora append-only protegida a nivel de base de datos.
- Búsqueda y filtros.

## Fase 3 — Documentos

- [x] Carga validada de PDF/DOCX en cuarentena y hash SHA-256.
- [x] Exportación local opcional a una raíz autorizada de VELUM.
- [ ] Antivirus, OCR, etiquetas y versiones.
- Plantillas DOCX y generación controlada.
- Integración local opcional con VELUM.

## Fase 4 — Términos de Puerto Rico

- [x] Regla 68.1 versionada con fuente oficial y explicación.
- [x] Cierres suministrados por el usuario y tratados como datos verificables.
- [ ] Reglas sustantivas específicas de procedimiento civil y administrativo.
- [ ] Ingestión autenticada de órdenes de cierre y calendarios judiciales.
- Autoridades citadas y pruebas de casos límite.
- Confirmación obligatoria por abogado.

## Fase 5 — Interfaz y colaboración

- [x] Dashboard inicial y cronología del caso.
- [x] Calendario por bufete y expediente con exportación privada `.ics`.
- [x] Confirmación profesional de términos, recordatorios y conflictos de horario.
- Calendario, alertas y asignaciones.
- [x] Detección explicable de expedientes relacionados.
# Integraciones

- [x] Conexiones cifradas y aisladas por bufete/usuario
- [x] Google OAuth con permisos mínimos
- [x] Sincronización saliente de Google Calendar
- [x] Envío de Gmail sin lectura general del buzón
- [x] WhatsApp Business templates y webhooks firmados
- [ ] Renovación automática de tokens y canales de Google
- [x] Cola persistente y deduplicada con reintentos limitados
- [x] Panel frontend para iniciar y revocar conexiones
- [x] Selector validado de Google Calendar
- [ ] Dead-letter queue y alertas operacionales
- [ ] Finalizar Embedded Signup dentro del frontend con el SDK oficial de Meta
- [ ] Asociación humana de comunicaciones entrantes
