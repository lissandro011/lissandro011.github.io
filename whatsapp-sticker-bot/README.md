# Licha.bot: stickers para WhatsApp

Un bot de WhatsApp hecho con [neonize](https://github.com/krypton-byte/neonize) (cliente async) que convierte imágenes, videos y GIFs en stickers y los manda en el mismo chat.

- **Imagen** con el texto `.sticker` (o respondiendo a una imagen con `.sticker`): sticker WebP de 512×512, mantiene la proporción con fondo transparente y pesa menos de 100 KB.
- **Video o GIF** de hasta 10 s: sticker animado WebP de 512×512 y menos de 500 KB.
- **Marca de Licha.bot** en cada sticker. Al tocarlo, WhatsApp muestra "Licha.bot" como paquete y autor (metadatos EXIF). Además lleva el texto "Licha.bot" en la esquina inferior derecha.
- Ignora sus propios mensajes y todo lo que no sea el comando. Si algo falla, responde con un error corto y deja el detalle en el log.
- Se vincula con un **código de emparejamiento** (sin QR). La sesión se guarda en SQLite, así que no hace falta volver a vincular.

## Requisitos

- Python 3.10 o más nuevo.
- `ffmpeg` y `ffprobe` con soporte WebP (los paquetes de Debian, Ubuntu y Homebrew lo traen).
- `libmagic` (la usa neonize).
- Linux x86_64 o ARM64 (por ejemplo, Raspberry Pi OS de 64 bits) o macOS. En Windows, usá WSL o Docker.

## Instalación

Debian o Ubuntu:

```bash
sudo apt install python3 python3-venv ffmpeg libmagic1
```

macOS:

```bash
brew install python ffmpeg libmagic
```

Después, en la carpeta del bot:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # y completá WA_PHONE_NUMBER
```

## Configuración

Todo se configura con variables de entorno. También se puede usar un archivo `.env` en la carpeta del bot, y las variables reales tienen prioridad sobre ese archivo.

| Variable | Por defecto | Para qué sirve |
|---|---|---|
| `WA_PHONE_NUMBER` | (vacío) | Número del bot en formato internacional, solo dígitos. Solo hace falta para vincular. |
| `WA_SESSION_DB` | `data/session.sqlite3` | SQLite con la sesión. Si la ruta es relativa, se toma desde la carpeta del bot. |
| `STICKER_COMMAND` | `.sticker` | Comando. No distingue mayúsculas. |
| `STICKER_PACK_NAME` | `Licha.bot` | Nombre del paquete que muestra WhatsApp. |
| `STICKER_PACK_PUBLISHER` | `Licha.bot` | Autor que muestra WhatsApp. |
| `STICKER_WATERMARK` | `Licha.bot` | Texto visible en la esquina. Dejalo vacío para no dibujarlo. |
| `STICKER_IMAGE_MAX_KB` | `100` | Tamaño objetivo de los stickers estáticos. |
| `STICKER_ANIMATED_MAX_KB` | `500` | Tamaño objetivo de los animados. |
| `STICKER_MAX_VIDEO_SECONDS` | `10` | Duración máxima del video. Hasta medio segundo de más se acepta y se recorta. |
| `MAX_DOWNLOAD_MB` | `25` | Archivos más pesados se rechazan sin descargarlos. |
| `MAX_CONCURRENT_CONVERSIONS` | `2` | Cuántas conversiones corren a la vez. |
| `PAIR_TIMEOUT_SECONDS` | `180` | Cuánto se espera a que ingreses el código de vinculación. |
| `LOG_LEVEL` / `NEONIZE_LOG_LEVEL` | `INFO` / `WARNING` | Nivel de log del bot y de la conexión con WhatsApp. |

**Formato del número en Argentina:** 54 + 9 + código de área sin el 0 + número sin el 15. Por ejemplo, `5491123456789`.

## Vincular el número

1. Poné el número en `WA_PHONE_NUMBER` (en el `.env`).
2. Corré el bot:

   ```bash
   python bot.py
   ```

3. En el log aparece:

   ```
       CÓDIGO DE VINCULACIÓN:  ABCD-EFGH
   ```

4. En el teléfono de ese número, andá a **WhatsApp > Dispositivos vinculados > Vincular un dispositivo > Vincular con el número de teléfono** e ingresá el código. Tenés unos 2 minutos y medio. Si vence, el bot se detiene y avisa: volvé a correrlo para pedir otro.
5. Cuando veas `¡Número vinculado!` y después `Conectado a WhatsApp`, ya está. En "Dispositivos vinculados" del teléfono aparece como **Licha.bot**.

La sesión queda en `data/session.sqlite3`, así que la próxima vez arranca directo, sin código. **Ese archivo es una credencial:** quien lo tenga puede usar tu WhatsApp. No lo compartas ni lo subas a git (el `.gitignore` ya lo excluye).

Para volver a vincular desde cero, detené el bot, borrá `data/session.sqlite3` y repetí los pasos. Si desvinculás el bot desde el teléfono, el bot se detiene con el código de salida 2 y en el próximo arranque pide un código nuevo.

## Usarlo

En cualquier chat privado o grupo donde esté el número del bot:

- Mandá una foto, un video o un GIF con el texto `.sticker`.
- O respondé a una foto, un video o un GIF con `.sticker`.

El bot contesta con el sticker citando tu mensaje. Si algo no se puede, responde con un aviso corto, por ejemplo:

- "El video dura 15 s; el máximo es 10 s."
- "No pude descargar el archivo (puede que ya no esté disponible)."
- "No hago stickers de fotos o videos de 'ver una vez'."

> **Para probarlo:** los mensajes que salen del propio número del bot se ignoran, incluso los que mandás desde el teléfono vinculado. Probalo escribiéndole desde **otro número**.

## Probar sin WhatsApp

La conversión vive en `sticker.py`, que no depende de WhatsApp:

```bash
python sticker.py foto.jpg sticker.webp     # imagen -> sticker estático
python sticker.py video.mp4 sticker.webp    # video/GIF -> sticker animado
python sticker.py foto.jpg sticker.webp --marca ""   # sin la marca visible
```

Imprime el tamaño, la cantidad de cuadros y los metadatos del resultado. Para correr los tests (imágenes, videos, interpretación de mensajes, vinculación y el handler completo con un cliente simulado):

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Dejarlo corriendo 24/7

### Opción A: systemd (un servidor o una Raspberry Pi con Linux)

```bash
# 1. Usuario sin privilegios y carpeta del bot
sudo useradd --system --home-dir /opt/licha-sticker-bot --shell /usr/sbin/nologin licha
sudo mkdir -p /opt/licha-sticker-bot/data
sudo cp bot.py config.py sticker.py requirements.txt .env.example /opt/licha-sticker-bot/
cd /opt/licha-sticker-bot

# 2. Dependencias
sudo apt install python3-venv ffmpeg libmagic1
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements.txt

# 3. Configuración (completá WA_PHONE_NUMBER)
sudo cp .env.example .env
sudo nano .env
sudo chown -R licha:licha data .env
sudo chmod 600 .env

# 4. Servicio
sudo cp /ruta/al/repo/whatsapp-sticker-bot/deploy/licha-sticker-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now licha-sticker-bot

# 5. Mirá el log: la primera vez muestra el código de vinculación
journalctl -u licha-sticker-bot -f
```

Qué hace el servicio (`deploy/licha-sticker-bot.service`):

- Arranca con la máquina, cuando hay red.
- Si el bot se cae, lo reinicia a los 10 s.
- No se reinicia en bucle cuando hace falta vincular (código de salida 2). En ese caso, `sudo systemctl restart licha-sticker-bot` pide un código nuevo y lo ves con `journalctl`.
- Corre con un usuario sin privilegios que solo puede escribir en `data/`.

Comandos útiles: `systemctl status licha-sticker-bot` y `sudo systemctl restart licha-sticker-bot` (por ejemplo, después de copiar una versión nueva de los `.py`).

### Opción B: Docker

```bash
cp .env.example .env               # completá WA_PHONE_NUMBER
docker compose build

# Primera vez: corre en primer plano y muestra el código de vinculación.
# Cuando diga "Conectado a WhatsApp", cortalo con Ctrl+C.
docker compose run --rm bot

# Desde ahora, en segundo plano y para siempre:
docker compose up -d
docker compose logs -f
```

- La sesión vive en el volumen `session`, que sobrevive a reinicios y rebuilds.
- `restart: unless-stopped` levanta el contenedor si se cae o si reinicia la máquina (con Docker habilitado al inicio: `sudo systemctl enable docker`).
- Para actualizar: `docker compose build && docker compose up -d`.

Si desvinculás el bot desde el teléfono, el contenedor sale con código 2 y Docker lo vuelve a levantar. Cada ~3 minutos va a pedir un código nuevo (aparece en `docker compose logs -f`). Si no querés volver a vincularlo, frenalo con `docker compose stop`.

## Notas

- WhatsApp no tiene una API oficial de bots para cuentas comunes. neonize usa el protocolo de WhatsApp Web (multidispositivo), y WhatsApp puede restringir números que se comporten como spam. Conviene usar un número secundario.
- Si el teléfono principal pasa unos 14 días sin conexión, WhatsApp desvincula los dispositivos y hay que volver a vincular.
- No se hacen stickers de fotos o videos de "ver una vez", para respetar la intención de quien los mandó.
