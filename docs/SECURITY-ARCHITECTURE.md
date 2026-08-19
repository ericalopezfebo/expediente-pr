# Arquitectura de seguridad

## Estado actual

La versión 0.1 es un prototipo sin autenticación y con almacenamiento en memoria.
Solo debe ejecutarse con datos ficticios en un entorno local de desarrollo.

## Requisitos antes de manejar información real

1. Persistencia en PostgreSQL con `firm_id` obligatorio y políticas de aislamiento.
2. Autenticación multifactor y sesiones seguras.
3. Control de acceso por roles: administrador, abogado, personal y cliente.
4. Cifrado en tránsito y en reposo.
5. Almacenamiento privado de documentos con enlaces de corta duración.
6. Bitácora append-only para acceso, descarga, cambio y eliminación.
7. Antivirus, validación de tipo real y límites para archivos cargados.
8. Política de retención y eliminación verificable.
9. Copias de seguridad cifradas y prueba periódica de restauración.
10. Evaluación separada de cada proveedor externo y flujo de IA.

## Límites de la automatización jurídica

El sistema no debe presentar escritos, confirmar términos ni enviar información a
terceros sin una acción afirmativa de una persona autorizada. Todo cálculo de término
debe almacenar la entrada, regla, fuente, versión, ajustes y aprobación final.

