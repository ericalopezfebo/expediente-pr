# Integraciones de Google y WhatsApp

## Modelo de distribución

Expediente PR no incluye credenciales universales. Cada instalación registra sus
propias aplicaciones en Google Cloud y Meta, acepta los términos de esos
proveedores y mantiene los secretos fuera de Git. Para una oferta SaaS, el
operador debe completar por separado las revisiones y verificaciones exigidas.

## Preparación

1. Copie `.env.example` a su sistema de secretos; no lo convierta en un archivo
   público con valores reales.
2. Genere una clave Fernet y un secreto OAuth aleatorio.
3. Use HTTPS público para callbacks y webhooks.
4. Ejecute `alembic upgrade head`.

Cambiar la clave Fernet sin un proceso de rotación vuelve ilegibles los tokens
existentes. Mantenga una copia protegida dentro del plan de recuperación.

## Google

1. Cree un proyecto de Google Cloud.
2. Habilite Google Calendar API y Gmail API.
3. Configure la pantalla de consentimiento y un cliente OAuth de tipo web.
4. Registre exactamente `GOOGLE_REDIRECT_URI`.
5. Configure `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`.
6. Desde la aplicación, abra `GET /integrations/google/authorize` y visite la URL.

El producto solicita únicamente:

- `calendar.events`
- `gmail.send`
- identidad básica para mostrar la cuenta autorizada

No se solicita lectura del buzón. Una distribución pública puede requerir
verificación de Google por utilizar datos de usuario.

Para sincronizar un evento confirmado:

`POST /integrations/google/calendar/events/{event_id}`

Para enviar un correo:

`POST /integrations/google/gmail/send`

El dashboard permite escoger cualquiera de los calendarios donde la cuenta tenga
permiso de escritura. La selección se valida nuevamente contra Google antes de
guardarse.

Configure `GOOGLE_CALENDAR_WEBHOOK_URL` con una dirección HTTPS pública y pulse
“Activar sincronización”. Google notificará cambios sin incluir el contenido del
evento. El worker vuelve a consultar exclusivamente los eventos que Expediente PR
ya había enlazado, evitando importar el calendario personal completo. Las
suscripciones de Google expiran y deben renovarse operacionalmente.

## Worker de recordatorios

Ejecute periódicamente:

`expediente-worker --once`

El worker:

- identifica recordatorios próximos;
- crea un trabajo único por evento, antelación y canal;
- utiliza la conexión Google de la persona asignada;
- envía un aviso sin título, cliente, foro ni número de caso;
- conserva intentos y errores para operación;
- cancela trabajos correspondientes a eventos cancelados.
- procesa cambios pendientes de los eventos Google ya vinculados.

La deduplicación evita reencolar el mismo recordatorio. No equivale a garantía
matemática de entrega única cuando un proveedor acepta una solicitud pero la
respuesta se pierde; esa situación debe tratarse como entrega incierta.

## WhatsApp Business Platform

1. Cree una aplicación empresarial en Meta.
2. Configure WhatsApp Embedded Signup y obtenga `META_CONFIG_ID`.
3. Configure el callback del webhook como `/webhooks/whatsapp`.
4. Suscriba la aplicación y use el mismo `META_WEBHOOK_VERIFY_TOKEN`.
5. El administrador abre `GET /integrations/whatsapp/signup`.
6. El frontend entrega el código, WABA ID y phone number ID a
   `POST /integrations/whatsapp/connect`.

Los envíos utilizan plantillas aprobadas:

`POST /integrations/whatsapp/messages`

Los mensajes entrantes se registran como `received_unassigned`; una persona debe
asociarlos al expediente correcto. No se infiere automáticamente una relación
abogado-cliente a partir de un número telefónico.

## Operación y privacidad

- Mantenga tokens cifrados y secretos en un gestor de secretos.
- Solicite consentimiento documentado antes de enviar mensajes.
- No coloque hechos sensibles en asuntos, previews o plantillas.
- Defina retención y legal hold antes de conservar contenido completo.
- Revise periódicamente permisos concedidos y conexiones revocadas.
- Configure alertas para errores de proveedores y webhooks rechazados.
- Use un dominio y una política de privacidad verificables antes de publicar OAuth.

La aceptación de un mensaje por Google o Meta no demuestra entrega, lectura ni
cumplimiento de un término judicial.
