# Conexión de Power BI Desktop a PostgreSQL (Neon)

Guía para conectar Power BI Desktop a la base del pipeline en **modo Import** usando el
rol de **solo lectura** `powerbi_lector`, que únicamente puede leer el esquema `reporting`.

> Esta guía se ampliará en la fase 5 con las vistas del modelo estrella y las medidas DAX.

## 1. Datos que necesitas (no los compartas ni los subas al repo)

| Campo | Dónde obtenerlo |
|---|---|
| **Servidor** | **Solo el host**, nunca la cadena completa `postgresql://…`. Es el texto entre `@` y `/neondb` de `DATABASE_URL_UNPOOLED` (en `.env`). Termina en `.sa-east-1.aws.neon.tech` y **no** contiene `-pooler`. También aparece en Neon Console → *Connect* (desactiva *Connection pooling*). |
| **Base de datos** | `neondb` |
| **Usuario** | `powerbi_lector` |
| **Contraseña** | En `.env`, variable `POWERBI_LECTOR_PASSWORD` |

Usa la conexión **directa** (sin `-pooler`): el modo Import abre una conexión, descarga los
datos y la cierra, así que no necesita pooler.

## 2. Pasos en Power BI Desktop

1. **Inicio → Obtener datos → Más… → Base de datos PostgreSQL → Conectar.**
2. **Servidor:** pega el host (sin `postgresql://`, sin usuario y sin `/neondb`).
   El puerto por defecto (5432) no hace falta escribirlo.
3. **Base de datos:** `neondb`.
4. **Modo de conectividad de datos:** **Importar**.
   No uses DirectQuery: mantendría el cómputo de Neon encendido y consumiría horas del plan gratuito.
5. **Aceptar.** En la ventana de credenciales elige **Base de datos** y escribe
   usuario `powerbi_lector` y su contraseña.
6. **Cifrado (SSL):** deja marcada la opción de **cifrar la conexión**. Neon exige SSL.
7. En el **Navegador** expande `reporting` y marca `vw_prueba_conexion` → **Cargar**.
   Debe aparecer 1 fila con `base_de_datos = neondb` y `usuario = powerbi_lector`.

> La primera conexión puede tardar unos segundos: Neon "despierta" el cómputo si estaba
> suspendido (scale to zero).

## 3. Solución de problemas

| Error | Causa probable | Solución |
|---|---|---|
| *"Error no recuperable durante una búsqueda en base de datos"* | En **Servidor** se pegó la cadena completa `postgresql://usuario:clave@host…` y Power BI la interpreta como nombre de host (falla el DNS) | Escribe solo el host. **Si la cadena incluía una contraseña**: borra ese origen en *Archivo → Opciones y configuración → Configuración de origen de datos → Borrar permisos* y cambia la contraseña de ese rol. |
| *"Endpoint ID is not specified"* | El cliente no envió SNI en TLS | En el campo **Contraseña** escribe `endpoint=<endpoint_id>$<contraseña>`. `<endpoint_id>` es la primera parte del host (`ep-...`, sin el resto del dominio). Es la alternativa documentada por Neon. |
| *"The remote certificate is invalid"* | Validación del certificado | Actualiza Power BI Desktop. Como último recurso, en *Archivo → Opciones → Seguridad de datos* revisa la configuración de certificados. **No** desactives el cifrado. |
| *"permission denied for schema …"* | Intentas leer fuera de `reporting` | Es lo esperado: `powerbi_lector` solo ve `reporting`. |
| *"password authentication failed"* | Contraseña o usuario incorrectos | Revisa `.env`. Para regenerarla: borra la línea `POWERBI_LECTOR_PASSWORD` de `.env` y ejecuta `python -m etl.crear_rol_powerbi`. |
| Tiempo de espera agotado | El cómputo se estaba despertando | Vuelve a intentar. |

## 4. Buenas prácticas de consumo (plan gratuito de Neon)

- Refresca **manualmente** solo cuando el pipeline haya cargado datos nuevos.
- Cada refresco transfiere datos desde Neon (egress, 5 GB al mes en el plan gratuito).
  Las vistas de `reporting` exponen solo las columnas necesarias para reducirlo.
- Cierra Power BI o cualquier cliente SQL cuando no lo uses: una conexión abierta impide
  que Neon suspenda el cómputo.
