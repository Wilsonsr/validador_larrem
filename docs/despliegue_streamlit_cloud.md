# Publicar el validador en Streamlit Community Cloud

La aplicación puede usarse en el equipo (con `iniciar_validador.bat`) o publicada en Streamlit Community Cloud para que el equipo la abra desde el navegador sin instalar nada.

## Consideraciones antes de publicar

- **Datos personales.** En la versión publicada, las bases se suben y se procesan en servidores de Streamlit (Snowflake) fuera de la red de la SDS. Confirme que esto está permitido por la política de tratamiento de datos de la entidad antes de usarla con bases reales. Si no lo está, use la versión local.
- **Sin historial en disco.** El almacenamiento del servidor no es persistente. Para comparar cortes, conserve cada reporte descargado y súbalo en la siguiente validación.
- **Una sola app privada.** En el plan gratuito solo se puede tener una aplicación privada a la vez.
- **Nunca suba bases ni reportes al repositorio.** El `.gitignore` excluye `*.xlsx` y `resultados/ejecuciones/`.

## Pasos

1. Cree un repositorio **privado** en GitHub y suba el contenido de esta carpeta (sin `.venv`, sin bases y sin resultados).
2. Ingrese a <https://share.streamlit.io> con la cuenta de GitHub y elija **Create app** → *Deploy a public app from GitHub*.
3. Seleccione el repositorio, la rama y el archivo principal `app.py`. En *Advanced settings* elija Python 3.12.
4. Despliegue. Las dependencias se instalan desde `requirements.txt`.
5. Las apps de un repositorio privado son privadas por defecto. Para dar acceso: **Share** → escriba el correo de cada persona → **Invite**. Si el correo es de Google, la persona ingresa con Google; si no, recibe un enlace de un solo uso por correo.
6. Para actualizar reglas: modifique los YAML en el repositorio y haga *push*. La aplicación se reinicia con la nueva configuración (la versión aparece en la barra lateral y en cada reporte).

El tamaño máximo de carga está configurado en 200 MB por archivo (`.streamlit/config.toml`).

Referencia: <https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app>
