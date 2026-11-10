# Licha Bot 🤖

Bot de WhatsApp que hace stickers, pensado para correr en una PC con Windows y preparado para sumarle comandos nuevos.

- **Foto → sticker**: mandá una foto con `!s` (o respondé a una foto con `!s`).
- **Video o GIF → sticker animado**: igual, con videos o GIFs (se usan los primeros 10 segundos).
- **Sticker → sticker con tu nombre**: respondé a cualquier sticker con `!s Mi pack | Mi nombre`.
- **Sticker → foto**: respondé a un sticker con `!imagen`.
- **Para jugar y para grupos**: dado, moneda, bola 8, elegir, ranking, excusas, votar reglas (`!decreto`) y armar planes (`!confirmo`), con respuestas de amigo argentino que se dan cuenta de lo que acaba de pasar.
- **Solo el dueño lo mete en grupos**: si lo agrega otra persona, le pide permiso al dueño y, si no lo autoriza, se va.
- **Comandos nuevos**: se agregan con un archivo `.py` en la carpeta `comandos` y aparecen solos en `!menu`.

Está hecho en Python con [neonize](https://github.com/krypton-byte/neonize), que se conecta a WhatsApp como un "dispositivo vinculado" (igual que WhatsApp Web). Los stickers se hacen con Pillow y PyAV, así que **no hace falta instalar ffmpeg ni ningún otro programa** aparte de Python.

---

## Qué necesitás

- Una PC con **Windows 10 u 11 de 64 bits** y conexión a internet. Va a ser el "servidor": el bot funciona mientras esté prendida.
- Un **celular con el chip del bot** y WhatsApp instalado. Después de vincularlo, el bot funciona aunque el celular esté apagado, pero WhatsApp desvincula los dispositivos si ese celular pasa **14 días sin conectarse**. Prendelo de vez en cuando.
- Otro número (el tuyo) para probarlo.

---

## Instalación paso a paso

### Paso 1: activar WhatsApp en el chip del bot

1. Poné el chip en un celular. Puede ser uno viejo. Si tu celular es dual SIM, también podés usar **WhatsApp Business** con el segundo chip, al lado de tu WhatsApp normal.
2. Instalá WhatsApp (o WhatsApp Business) y registrá el número del chip con el SMS de verificación.
3. Poné de nombre **Licha Bot** y, si querés, una foto de perfil.

### Paso 2: instalar Python en la PC

Licha Bot necesita Python 3.11 o más nuevo. Recomendado: **Python 3.13**.

**Opción A (la más fácil):** abrí el menú Inicio, buscá **PowerShell**, abrilo y escribí:

```bash
winget install -e --id Python.Python.3.13
```

**Opción B:** entrá a <https://www.python.org/downloads/windows/>, bajá el instalador "Windows installer (64-bit)" de la última versión 3.13 y, en la primera pantalla del instalador, **marcá la casilla "Add python.exe to PATH"** antes de tocar "Install Now".

### Paso 3: descargar Licha Bot

1. Entrá a <https://github.com/lissandro011/lissandro011.github.io>, tocá el botón verde **Code** y después **Download ZIP**. (Si Licha Bot todavía no está en la rama principal, elegí primero la rama donde está en el selector de ramas).
2. Antes de descomprimir: clic derecho en el ZIP > **Propiedades** > si abajo aparece **Desbloquear**, marcalo y tocá **Aceptar**. Así Windows no bloquea los `.bat`.
3. Descomprimí el ZIP y copiá la carpeta **`licha-bot`** a **`C:\LichaBot`**.
   Conviene una ruta corta, sin espacios ni tildes. Te tiene que quedar `C:\LichaBot\iniciar.bat`, `C:\LichaBot\instalar.bat`, etc.

### Paso 4: instalar

Hacé doble clic en **`instalar.bat`**.

- Si Windows muestra "Windows protegió su PC", tocá **Más información** > **Ejecutar de todas formas**.
- Crea un entorno de Python propio del bot (la carpeta `.venv`), descarga las librerías y crea el archivo `config.toml`. Tarda unos minutos.
- Al final pregunta si querés abrir `config.toml`: poné **S**.

### Paso 5: configurar

En `config.toml` (se abre con el Bloc de notas) completá:

```toml
numero = "5491123456789"      # el número del CHIP DEL BOT
duenos = ["5491198765432"]    # TU número personal
```

**Formato del número:** código de país + número, solo dígitos y sin `+`. En Argentina: **54 + 9 + código de área sin el 0 + número sin el 15**. Por ejemplo, (011) 15-2345-6789 se escribe `5491123456789`, y (0341) 15-555-1234 se escribe `5493415551234`.

`duenos` es para los comandos de dueño (`!reiniciar`, `!apagar`, `!autorizar`) y para decidir en qué grupos se queda el bot (ver [Grupos](#grupos-solo-el-dueño-agrega-al-bot)). Las demás opciones (prefijos, nombre del paquete de stickers, marca de agua, etc.) están explicadas en el mismo archivo. Guardá con **Archivo > Guardar**.

### Paso 6: prender el bot y vincular el número

1. Hacé doble clic en **`iniciar.bat`**. Se abre una ventana negra y, en unos segundos, aparece:

   ```
     ╔══════════════════════════════════════════════════════╗
     ║   CÓDIGO PARA VINCULAR LICHA BOT:   ABCD-EFGH        ║
     ╚══════════════════════════════════════════════════════╝
   ```

   El teléfono del chip también puede recibir una notificación de WhatsApp para vincular.
2. En el **celular con el chip del bot**, abrí WhatsApp:
   - **Android:** ⋮ (arriba a la derecha) > **Dispositivos vinculados** > **Vincular un dispositivo** > abajo, **Vincular con el número de teléfono**.
   - **iPhone:** **Configuración** > **Dispositivos vinculados** > **Vincular un dispositivo** > **Vincular con el número de teléfono**.
3. Escribí el código de 8 caracteres que muestra la ventana. Tenés 3 minutos. Si se vence, cerrá la ventana y abrí `iniciar.bat` de nuevo.
4. Cuando la ventana diga **"✅ Licha Bot está conectado y escuchando"**, ya está. La sesión queda guardada y la próxima vez arranca directo, sin código.

> Si dejás `numero` vacío, en lugar del código aparece un **QR** (en la ventana y en la imagen `datos\qr.png`) para escanear desde **Dispositivos vinculados** > **Vincular un dispositivo**.

### Paso 7: probarlo

Desde **otro número** (el bot no contesta sus propios mensajes):

1. Escribile `!menu` por privado: te contesta la lista de comandos.
2. Mandale una foto con el texto `!s`: te la devuelve como sticker.
3. Agregalo a un grupo **desde tu número de dueño** y mandá una foto con el texto `!s`.

### Paso 8: dejarlo prendido 24/7

1. **Que arranque solo:** doble clic en **`activar_inicio_automatico.bat`**. Desde ahora, cada vez que inicies sesión en Windows, el bot se abre minimizado. Para sacarlo: `desactivar_inicio_automatico.bat`.
2. **Que la PC no se suspenda:** Configuración > Sistema > **Inicio/apagado y batería** (o **Energía**) > "Suspender" o "Apagar pantalla y suspender": poné **Nunca** en suspender (la pantalla sí se puede apagar).
3. **Que Windows Update no la reinicie en cualquier momento:** Configuración > Windows Update > Opciones avanzadas > **Horas activas**.
4. Si el bot se cae o se corta internet, `iniciar.bat` lo vuelve a levantar solo a los 15 segundos.

Para apagarlo, cerrá su ventana (o mandale `!apagar` desde un número de dueño).

---

## Comandos

Los comandos funcionan con `!` o con `.` adelante (`!s` y `.s` son lo mismo). Se cambia en `prefijos` de `config.toml`.

**Para jugar**

| Comando | Qué hace |
|---|---|
| `!dado` · `!dado 20` · `!dado 2d6` | Tira un dado (de 6 caras, de las que digas, o varios juntos). |
| `!moneda` | Cara o cruz. Si tirás de nuevo enseguida, Licha se da cuenta. |
| `!8ball ¿pregunta?` | La bola 8 contesta sí, no o vemos. Reconoce el clásico "¿le escribo?". |
| `!elegir pizza, empanadas o sushi` | Elige una opción al azar. Separá con comas, `\|` o la palabra "o". |
| `!top5 más dormilones` | (Solo grupos) Ranking en broma: etiqueta a 5 integrantes al azar. `!top 3 ...` cambia la cantidad (de 2 a 10). |

**Para grupos**

| Comando | Qué hace |
|---|---|
| `!confirmo armar previa del sábado` | (Solo grupos) Abre una lista. Cada uno pone `!confirmo voy`, `!confirmo capaz` o `!confirmo me bajo`, o responde al mensaje de la lista con "voy", "capaz" o "me bajo". |
| `!confirmo` · `!confirmo cerrar` | Muestra el resumen o cierra la lista con el recuento final. |
| `!decreto El que llega tarde paga el hielo` | (Solo grupos) Propone una regla para votar. Se vota con `!decreto si` / `!decreto no`. |
| `!decreto estado` · `!decreto cerrar` | Muestra cómo va o cierra la votación (gana el sí si tiene más votos que el no). |
| `!excusa` | Una excusa lista para reenviar y bajarte del plan. Si pedís otra enseguida, te la cambia. |

Hay una lista y una votación abiertas por grupo. Las cierra quien las abrió, un admin del grupo o el dueño. Se guardan en `datos\licha.sqlite3`, así que sobreviven a un reinicio.

**Stickers**

| Comando | Qué hace |
|---|---|
| `!sticker` · `!s` | Foto, video o GIF → sticker. Mandalo como pie de la foto o respondiendo a una. |
| `!s recortar` | Igual, pero recorta al centro y llena el cuadrado (sin bordes transparentes). |
| `!s Mi pack \| Mi nombre` | Respondiendo a una foto o a un sticker: cambia el nombre del paquete y el autor que muestra WhatsApp. |
| `!imagen` · `!toimg` | Respondiendo a un sticker, lo devuelve como foto. |

**General y dueño**

| Comando | Qué hace |
|---|---|
| `!menu` | Lista de comandos. |
| `!ayuda sticker` | Cómo se usa un comando, con ejemplos. |
| `!ping` · `!estado` | Muestra si el bot está funcionando (`!estado` también dice hace cuánto está prendido). |
| `!reiniciar` · `!apagar` | (Solo dueños) Reinicia o apaga el bot. |
| `!autorizar` · `!rechazar` · `!grupos` | (Solo dueños) Deciden en qué grupos se queda el bot (ver abajo). |

Los stickers siempre se piden con `!sticker` (o `!s`), también por privado. Si querés que por privado cualquier foto vuelva como sticker sin escribir nada, poné `automatico_en_privado = true` en `config.toml`. Las fotos y videos de "ver una vez" nunca se usan.

### Grupos: solo el dueño agrega al bot

Con `solo_el_dueno_agrega = true` (sección `[grupos]` de `config.toml`, viene activado):

- Si **un dueño** agrega al bot a un grupo, se queda y saluda.
- Si lo agrega **otra persona**, el bot avisa en el grupo que necesita permiso y te manda por privado un mensaje con un código:
  - `!autorizar 1234` → se queda.
  - `!rechazar 1234` → se va del grupo.
  - Si no contestás en `minutos_para_autorizar` (10 por defecto), se va solo.
- Mientras espera, no le contesta a nadie en ese grupo (salvo a vos).
- Dentro de un grupo también podés mandar `!autorizar` (se queda) o `!salir` (se va). `!grupos` te muestra dónde está y qué grupos esperan permiso.
- Los grupos donde el bot ya estaba antes de esta función quedan autorizados solos.

Necesita tu número en `duenos`. Si la lista está vacía, la restricción no se aplica (y queda un aviso en el log).

**Si el aviso por privado no te llega**: el bot busca tu número en WhatsApp para escribirte al chat correcto, así que funciona igual si WhatsApp usa otra forma de tu número. Si aun así no sale (estaba sin conexión, el número está mal escrito, WhatsApp falló), no se pierde:

- Te lo cuenta en cuanto le escribas por privado, aunque sea un `!ping`.
- Lo reintenta cada vez que se reconecta.
- `!grupos` marca con ⚠️ los grupos de los que no te pudo avisar.
- Si tu número no está en WhatsApp, queda un error en el log (`logs\licha-bot.log`): revisá `duenos` en `config.toml`, en formato internacional, solo números y sin `+`.

---

## Agregar comandos nuevos

1. En la carpeta `comandos`, copiá **`_plantilla.py`** y ponele otro nombre **sin el guion bajo** adelante, por ejemplo `diversion.py`. Los archivos que empiezan con `_` no se cargan.
2. Editalo con el Bloc de notas (o mejor, con [Visual Studio Code](https://code.visualstudio.com/)). La plantilla trae ejemplos que funcionan (`!numero`, `!eco`, `!girar` y `!anuncio`) y la lista de todo lo que se puede usar.
3. Reiniciá el bot: cerrá la ventana y abrí `iniciar.bat`, o mandale `!reiniciar` desde un número de dueño.
4. El comando aparece solo en `!menu`.

Un comando es una función `async` con el decorador `@comando`:

```python
from licha_bot import ErrorUsuario, comando


@comando("hola", "buenas", categoria="Diversión", descripcion="Saluda", uso="{p}hola o {p}hola Juan")
async def hola(ctx):
    nombre = ctx.texto_args or ctx.nombre
    await ctx.responder(f"¡Hola, {nombre}! 👋")
```

- El primer nombre es el principal y los siguientes son alias (`!hola` y `!buenas`).
- `ctx.args` tiene las palabras después del comando y `ctx.texto_args`, todo el texto.
- `raise ErrorUsuario("mensaje")` corta el comando y le responde ese mensaje a quien lo usó.
- Opciones: `solo_grupos=True`, `solo_privado=True`, `solo_dueno=True` y `oculto=True` (no aparece en el menú).
- Para trabajar con fotos: `media = ctx.media()`, `datos = await ctx.descargar(media)` y `await ctx.enviar_imagen(...)` o `await ctx.enviar_sticker(...)`. Lo pesado se corre con `await ctx.en_segundo_plano(funcion, datos)` para no trabar al bot.
- Un comando puede tener su propia sección en `config.toml` y leerla con `ctx.config.seccion("nombre")`.

Si un archivo de comandos tiene un error, el bot arranca igual con los demás y el error queda en `logs\licha-bot.log`.

Si un comando necesita otra librería de Python, instalala dentro del entorno del bot. Abrí una terminal en `C:\LichaBot` y corré:

```bash
.venv\Scripts\python.exe -m pip install nombre-de-la-libreria
```

---

## Actualizar el bot

1. Cerrá la ventana del bot.
2. Descargá la versión nueva y copiá sus archivos encima de `C:\LichaBot`. **No borres** `config.toml` ni la carpeta `datos` (ahí está la sesión: si la borrás, hay que vincular de nuevo).
3. Abrí `instalar.bat` otra vez (actualiza las librerías y no toca tu configuración) y después `iniciar.bat`.

---

## Problemas comunes

**"No encontré Python 3.11 o más nuevo"**: instalá Python (paso 2). Si lo acabás de instalar, cerrá y volvé a abrir `instalar.bat`. Si lo instalaste desde python.org sin marcar "Add python.exe to PATH", volvé a correr el instalador, elegí **Modify** y activá esa opción.

**Falla la instalación de librerías**: revisá internet y volvé a abrir `instalar.bat`. Si el antivirus bloquea algún archivo de `.venv` (neonize trae una librería `.dll` que a veces da falsos positivos), agregá `C:\LichaBot` a las exclusiones del antivirus.

**No aparece el código, o aparece un error al pedirlo**: revisá `numero` en `config.toml` (formato `5491123456789`) y que ese número tenga WhatsApp activo.

**"No pude conectarme a WhatsApp"**: la PC no tiene internet o algo bloquea la conexión (un firewall o un proxy). El bot reintenta solo cada 15 segundos.

**El bot no contesta**:
- ¿Le escribiste desde otro número? El bot ignora los mensajes que salen de su propio número.
- ¿Usaste el prefijo? Es `!menu`, no `menu`.
- En grupos, fijate que `responder_en_grupos = true`.
- Si estuvo apagado, no responde mensajes de más de 10 minutos (`ignorar_mensajes_de_mas_de_minutos`).
- Mirá la ventana o `logs\licha-bot.log`: cada comando que recibe queda anotado.

**En un grupo no contesta nada**: si lo agregó alguien que no es dueño, está esperando tu permiso. Fijate en tu privado o mandale `!grupos` al bot.

**No me llegó el aviso para autorizar un grupo**: escribile cualquier cosa por privado (por ejemplo `!ping`) y te lo cuenta ahí mismo. Si pasa siempre, revisá `duenos` en `config.toml` y buscá `no está en WhatsApp` en `logs\licha-bot.log`.

**Pone ⏳ y no responde**: esa persona mandó comandos muy seguido. Hay que esperar 3 segundos entre comandos (`espera_entre_comandos`). Los dueños no tienen esa espera.

**"El bot se desvinculó" o pide vincular de nuevo**: pasa si lo sacás desde "Dispositivos vinculados" o si el celular del chip pasó 14 días sin conexión. Abrí `iniciar.bat` y vinculalo otra vez. Para empezar de cero: cerrá el bot, borrá `datos\sesion.sqlite3` y abrí `iniciar.bat`.

**Ver qué pasó**: todo queda en `logs\licha-bot.log`. Para más detalle, poné `nivel = "DEBUG"` en la sección `[registro]` de `config.toml`.

---

## Avisos importantes

- WhatsApp no tiene una API oficial de bots para cuentas comunes. neonize usa el mismo protocolo que WhatsApp Web, y WhatsApp puede **suspender números** que se comporten como spam. Por eso conviene un chip dedicado (como el tuyo). No lo uses para mandar mensajes masivos ni a gente que no le escribió.
- **`datos\sesion.sqlite3` es como la llave del WhatsApp del bot**: quien tenga ese archivo puede usar ese número. No lo compartas ni lo subas a internet. (`.gitignore` ya lo excluye del repositorio, junto con `config.toml`).

---

## Archivos

```
licha-bot/
├── instalar.bat                     instala todo (doble clic)
├── iniciar.bat                      prende el bot y lo reinicia si se cae
├── activar_inicio_automatico.bat    que arranque solo con Windows
├── desactivar_inicio_automatico.bat
├── config.ejemplo.toml              configuración de ejemplo (se copia a config.toml)
├── main.py                          punto de entrada (python main.py)
├── comandos/                        ← TUS COMANDOS: cada .py se carga solo
│   ├── stickers.py                  !sticker, !imagen y stickers automáticos
│   ├── general.py                   !menu, !ayuda, !ping
│   ├── diversion.py                 !dado, !moneda, !8ball, !elegir, !top5, !excusa
│   ├── grupo.py                     !decreto y !confirmo
│   ├── dueno.py                     !reiniciar, !apagar, !autorizar, !rechazar, !grupos
│   └── _plantilla.py                ejemplos para copiar (no se carga)
├── licha_bot/                       el motor del bot
│   ├── bot.py                       conexión con WhatsApp y despacho de comandos
│   ├── comandos.py                  @comando, @escuchar y carga de la carpeta comandos
│   ├── contexto.py                  el "ctx": responder, mandar stickers, descargar
│   ├── frases.py                    bolsas de frases y rachas ("tiró la moneda otra vez")
│   ├── almacen.py                   datos guardados: votaciones, listas, grupos (SQLite)
│   ├── guardia.py                   quién puede meter al bot en un grupo
│   ├── conversor.py                 foto/video/GIF → sticker (Pillow + PyAV)
│   ├── mensajes.py                  lectura de textos, fotos y respuestas
│   └── config.py                    lectura de config.toml
└── tests/                           pruebas automáticas (sin WhatsApp)
```

Se crean solos al usarlo: `.venv` (librerías), `config.toml`, `datos` (sesión de WhatsApp, votaciones, listas y grupos autorizados) y `logs`.

## Para programadores

Probar el conversor sin WhatsApp:

```bash
.venv\Scripts\python.exe -m licha_bot.conversor foto.jpg sticker.webp --marca "Licha Bot"
```

Correr las pruebas automáticas:

```bash
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

```bash
.venv\Scripts\python.exe -m pytest
```

Las pruebas automáticas pasan con neonize 0.10.0, Pillow 13 y PyAV 19 en Python 3.13.
