# Expediente PR

Plataforma open source de gestión de casos para abogados y bufetes de Puerto Rico.

> [!WARNING]
> Prototipo en desarrollo. Utiliza exclusivamente datos ficticios. No está autorizado
> para almacenar información confidencial ni para confirmar términos jurídicos.

## Propósito

Expediente PR busca reunir expedientes, asuntos relacionados, tareas, documentos y
términos en un sistema local-first, auditable y adaptado a la práctica puertorriqueña.
Los resultados jurídicos deben mostrar su fuente y explicación, y permanecer sujetos
a aprobación humana.

## Primera versión

- Crear y consultar expedientes.
- Persistencia local en SQLite o despliegue con PostgreSQL.
- Autenticación mediante tokens que solo se almacenan como hash.
- Roles para administración, abogacía, personal y clientes.
- Vincular números de casos relacionados.
- Crear y consultar tareas por expediente.
- Bitácora de creación de expedientes y tareas.
- Documentos PDF y DOCX en cuarentena con hash SHA-256.
- Exportación local opcional a una raíz previamente autorizada en VELUM.
- Dashboard inicial y sugerencias explicables de casos relacionados.
- Calendario jurídico por bufete y expediente, conflictos, alertas y exportación `.ics` privada.
- Calcular fechas provisionales con explicación y fuente indicada por el usuario.
- API documentada automáticamente con OpenAPI.
- Pruebas y validación continua en GitHub Actions.

## Inicio rápido

Requiere Python 3.11 o posterior.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn expediente_pr.main:app --reload
```

Abre `http://127.0.0.1:8000/docs` para probar la API.

Configura `EXPEDIENTE_BOOTSTRAP_TOKEN` y crea el primer bufete ficticio mediante
`POST /firms/register`. El token administrativo se muestra una sola vez. Utilízalo
como `Authorization: Bearer <token>` para crear usuarios y administrar expedientes.

Los tokens de API son una primera capa de autenticación para el backend. Antes de
uso productivo todavía hacen falta MFA, recuperación segura, rotación y sesiones
adecuadas para navegador.

Los documentos cargados permanecen en estado `quarantined`: no pueden descargarse
desde la API ni enviarse a proveedores externos. La exportación a VELUM solo copia el
archivo a `EXPEDIENTE_VELUM_ROOT`, que debe ser una carpeta local existente y también
estar autorizada expresamente en VELUM.

Los eventos jurídicos calculados se crean como `tentative` y solo una persona con rol
de abogado o administrador puede confirmarlos. La exportación `.ics` oculta títulos,
descripciones y ubicaciones por defecto. Las alertas quedan disponibles en
`/calendar/reminders/due` para que un worker autorizado las distribuya.

También puede iniciarse con Docker:

```bash
docker compose up --build
```

## Validación

```bash
ruff check .
pytest -q
```

## Diseño y próximos pasos

- [Hoja de ruta](docs/ROADMAP.md)
- [Arquitectura de seguridad](docs/SECURITY-ARCHITECTURE.md)
- [Política de seguridad](SECURITY.md)
- [Guía de contribución](CONTRIBUTING.md)

## Licencia

Apache License 2.0. Consulta [LICENSE](LICENSE).
## Integraciones opcionales

La versión 0.5 incorpora una base autohospedable para que cada profesional conecte
sus propias cuentas sin compartir contraseñas:

- Google Calendar: crea o actualiza eventos desde el calendario legal.
- Gmail: envía mensajes y registra metadatos de entrega en el expediente.
- WhatsApp Business Platform: onboarding mediante código de Meta, envío de
  plantillas aprobadas y recepción de webhooks firmados.
- iCalendar: exportación privada compatible con otros calendarios.

Las integraciones permanecen deshabilitadas hasta que el operador configure sus
propias aplicaciones OAuth. Copie solamente los nombres de variables de
`.env.example`; nunca publique sus valores reales.

### Controles de seguridad

- Los access y refresh tokens se cifran con Fernet antes de persistirse.
- El estado OAuth está firmado, ligado a bufete/usuario/proveedor y expira en diez minutos.
- Los permisos de Google se limitan a eventos de calendario y envío de Gmail.
- La aplicación no solicita lectura general del buzón.
- Los webhooks de WhatsApp requieren `X-Hub-Signature-256`.
- Las credenciales pueden revocarse con `DELETE /integrations/{provider}`.
- Los mensajes de WhatsApp deben usar plantillas aprobadas y evitar información
  confidencial en notificaciones.

Consulte [Configuración de integraciones](docs/INTEGRATIONS.md) para registrar las
aplicaciones de Google y Meta.
