# Instalar Licha.bot en Windows, paso a paso

Esta guía es para alguien que nunca programó. Vas a descargar una carpeta, hacer doble clic en tres archivos y responder un par de preguntas. Lleva entre 20 y 30 minutos.

Cuando termines, cualquier persona que le mande al número del bot una foto, un video corto o un GIF con el texto `.sticker` va a recibir ese archivo convertido en sticker, con la marca de Licha.bot.

---

## Antes de empezar

Necesitás cuatro cosas:

1. **Una PC con Windows 10 u 11 de 64 bits.** Para comprobarlo, andá a **Inicio > Configuración > Sistema > Información** y fijate en "Tipo de sistema". Tiene que decir *Sistema operativo de 64 bits, procesador basado en x64*. Si dice **ARM**, esta guía no te sirve (ver el README, opción Docker).
2. **Conexión a internet.**
3. **El número de WhatsApp que va a ser "el bot", con su teléfono a mano.**
4. **Otro número de WhatsApp para probarlo** (puede ser el de un amigo).

> **Qué número usar.** El bot funciona *dentro* de un WhatsApp: si alguien le escribe `.sticker` a ese número, el bot le contesta. Te recomendamos un **número secundario** (un chip aparte, o WhatsApp Business con otro número), por dos razones:
> - WhatsApp no tiene bots oficiales para cuentas comunes y podría bloquear un número que los use.
> - El bot ignora los mensajes que salen de su propio número. Por eso, para probarlo, le tenés que escribir desde otro.

Además, la PC tiene que estar prendida todo el tiempo que quieras que el bot funcione.

---

## Paso 1: Descargar el bot

1. Abrí este link en el navegador. Se descarga un archivo ZIP:
   **https://github.com/lissandro011/lissandro011.github.io/archive/refs/heads/claude/whatsapp-sticker-bot.zip**
   (Si no funciona porque el bot ya se pasó a la rama principal, usá este otro: https://github.com/lissandro011/lissandro011.github.io/archive/refs/heads/main.zip)
2. **Desbloquealo**, para que Windows no te frene después. Andá a la carpeta **Descargas**, hacé clic derecho en el ZIP y elegí **Propiedades**. Abajo de todo, tildá **Desbloquear** y tocá **Aceptar**. Si esa casilla no aparece, seguí igual.
3. Hacé clic derecho en el ZIP > **Extraer todo...** > **Extraer**.
4. En la carpeta que se abre, entrá a las carpetas hasta encontrar una que se llama **`whatsapp-sticker-bot`**. Adentro tiene archivos como `1-instalar`, `2-iniciar` y `bot.py`.
5. Pasá esa carpeta a un lugar fijo:
   1. Clic derecho en `whatsapp-sticker-bot` > **Copiar**.
   2. Abrí **Este equipo** > **Disco local (C:)**.
   3. Clic derecho en un espacio vacío > **Pegar**. Si Windows pide permiso, tocá **Continuar**.
   4. Clic derecho en la carpeta que pegaste > **Cambiar nombre** y poné **`LichaBot`**.

Tiene que quedarte la carpeta **`C:\LichaBot`** con estos archivos adentro:

| Archivo | Para qué sirve |
|---|---|
| `1-instalar` | Instala todo y te pregunta el número (paso 2) |
| `2-iniciar` | Prende el bot (paso 3) |
| `3-iniciar-con-windows` | Hace que el bot arranque solo con la PC (paso 5) |
| Los demás | Son el programa en sí. No hace falta tocarlos. |

> **¿Por qué no en el Escritorio o en Documentos?** Esas carpetas suelen estar sincronizadas con OneDrive, y OneDrive puede dañar el archivo donde el bot guarda la sesión de WhatsApp.

---

## Paso 2: Instalar (doble clic en `1-instalar`)

1. En `C:\LichaBot`, hacé **doble clic en `1-instalar`**.
2. Si aparece un cartel azul que dice **"Windows protegió su PC"**, tocá **Más información** y después **Ejecutar de todas formas**. Aparece porque el archivo vino de internet.
3. Se abre una ventana negra que te va guiando. Esto es lo que puede preguntarte:

   - **"No encontré Python... ¿Querés que lo instale ahora? [S,N]"**: apretá **S**. Python es el programa que hace funcionar al bot. Esperá a que termine; la instalación sigue sola.
   - **"[1/4] Instalando librerías"**: vas a ver mucho texto durante unos minutos. Es normal, no toques nada.
   - **"[2/4] No encontré ffmpeg. ¿Lo instalo ahora con winget? [S/n]"**: escribí **S** y apretá Enter. ffmpeg es el programa que convierte los videos. Si te pregunta si aceptás condiciones, aceptá.
   - **"[3/4] Número del bot"**: escribí el número del bot y apretá Enter. Va con el código de país, sin `+`, sin espacios, sin el 0 y sin el 15:

     | Si el número es... | Escribí |
     |---|---|
     | 011 15 2345-6789 (Buenos Aires) | `5491123456789` |
     | 0351 15 234-5678 (Córdoba) | `5493512345678` |
     | 0341 15 345-6789 (Rosario) | `5493413456789` |

     La regla en Argentina es: **54**, después **9**, después el código de área sin el 0 y al final el número sin el 15. Si te equivocás, el instalador te avisa y te deja escribirlo de nuevo.
   - **"[4/4] Revisión final"**: tienen que aparecer tres líneas con **[OK]** y el mensaje **"Todo listo"**. Apretá cualquier tecla para cerrar la ventana.

Si alguna línea dice **[!!]**, leé qué falta y buscalo en [Problemas comunes](#problemas-comunes). Podés volver a abrir `1-instalar` todas las veces que quieras; no se rompe nada.

---

## Paso 3: Prender el bot y vincular el número (doble clic en `2-iniciar`)

Esto se hace **una sola vez**. Después, el bot recuerda la sesión.

1. Hacé **doble clic en `2-iniciar`**. Se abre una ventana negra que dice "Prendiendo Licha.bot...".
2. A los pocos segundos aparece algo así:

   ```
   CÓDIGO DE VINCULACIÓN:  ABCD-EFGH
   ```

3. Agarrá el teléfono del número del bot:
   - **Android:** abrí WhatsApp, tocá los tres puntitos **⋮** (arriba a la derecha) > **Dispositivos vinculados** > **Vincular un dispositivo**. Si te lo pide, desbloqueá con tu huella o tu PIN. Cuando se abra la cámara, tocá abajo **"Vincular con el número de teléfono"** y escribí el código.
   - **iPhone:** abrí WhatsApp, andá a **Configuración** (abajo a la derecha) > **Dispositivos vinculados** > **Vincular un dispositivo** > **"Vincular con el número de teléfono"** y escribí el código.
4. **Tenés unos 2 minutos.** Si se vence, la ventana te avisa: cerrala y abrí `2-iniciar` de nuevo para pedir otro código.
5. Si salió bien, la ventana dice **"¡Número vinculado!"** y después **"Conectado a WhatsApp"**. En el teléfono, dentro de "Dispositivos vinculados", vas a ver **Licha.bot**.

> **Mientras quieras que el bot funcione, esa ventana tiene que seguir abierta.** Podés minimizarla, pero si la cerrás, el bot se apaga.

---

## Paso 4: Probarlo

Desde **otro** teléfono, o pidiéndole a un amigo:

1. Mandale al número del bot una foto con el texto **`.sticker`** (con el punto adelante). En unos segundos le llega el sticker.
2. Probá también con un video corto o un GIF de hasta 10 segundos.
3. Otra forma: respondé a una foto que ya esté en el chat escribiendo `.sticker`.

Si tocás el sticker, WhatsApp muestra **Licha.bot** como nombre del paquete. También funciona en grupos donde esté el número del bot. En la ventana del bot vas a ver una línea por cada pedido.

---

## Paso 5: Que arranque solo (recomendado)

1. Hacé **doble clic en `3-iniciar-con-windows`**. Te avisa "Listo".
2. Desde ahora, cada vez que inicies sesión en Windows, el bot se prende solo. Su ventana queda minimizada en la barra de tareas. Si se cae por un error, se vuelve a prender a los 10 segundos.
3. **Configurá la PC para que no se suspenda:**
   - **Windows 11:** Inicio > Configuración > Sistema > **Energía y batería** > Pantalla y suspensión > "Poner mi dispositivo en suspensión después de" > **Nunca**.
   - **Windows 10:** Inicio > Configuración > Sistema > **Inicio/apagado y suspensión** > Suspensión > **Nunca**.
   - Que se apague la pantalla no molesta.
   - **En una notebook:** dejala enchufada. Al cerrar la tapa se suspende; para evitarlo, andá a Panel de control > Hardware y sonido > Opciones de energía > **"Elegir el comportamiento del cierre de la tapa"** y elegí "No hacer nada".
4. Si la PC se reinicia (por ejemplo, por una actualización de Windows), el bot vuelve a arrancar cuando alguien inicia sesión, es decir, cuando ponés tu PIN o contraseña.

Para desactivarlo, abrí `3-iniciar-con-windows` de nuevo y respondé **S**.

---

## Uso de todos los días

- **Apagar el bot:** cerrá su ventana.
- **Prenderlo:** doble clic en `2-iniciar`, o simplemente iniciá sesión si hiciste el paso 5.
- **Una sola ventana a la vez.** Si abrís una segunda, avisa "Ya hay otra ventana de Licha.bot abierta" y no arranca.
- **Historial del bot:** queda en `C:\LichaBot\data\bot.log` y lo podés abrir con el Bloc de notas. Si algo falla, ahí está el detalle.

---

## Problemas comunes

**Aparece "Windows protegió su PC".**
Tocá **Más información** > **Ejecutar de todas formas**.

**El instalador no ofrece instalar Python, o la instalación falla.**
Instalalo a mano:
1. Entrá a https://www.python.org/downloads/ y tocá el botón amarillo **Download Python**.
2. Abrí el archivo que se descargó.
3. **Abajo de todo, tildá "Add python.exe to PATH"**. Esto es importante.
4. Tocá **Install Now** y, cuando termine, **Close**.
5. Volvé a abrir `1-instalar`.

**Dice [!!] ffmpeg, o no se instala.**
Instalalo a mano:
1. Entrá a https://www.gyan.dev/ffmpeg/builds/ y, en la sección *release builds*, bajá **`ffmpeg-release-essentials.zip`**.
2. Clic derecho en el ZIP > Extraer todo > Extraer.
3. Mové la carpeta que se creó (empieza con `ffmpeg`) **adentro de `C:\LichaBot`**.
4. Volvé a abrir `1-instalar`. Tiene que decir **[OK] ffmpeg**.

**Me equivoqué con el número.**
Abrí `1-instalar` y escribí el número correcto cuando te lo pregunte. Si el bot ya estaba vinculado con el número equivocado, además tenés que cerrar el bot, borrar la carpeta `C:\LichaBot\data` y abrir `2-iniciar` para vincular de nuevo.

**El código venció antes de que lo escribiera.**
Cerrá la ventana y abrí `2-iniciar` otra vez.

**Días después, la ventana dice "Hay que vincular el número".**
Pasa si quitaste "Licha.bot" de los dispositivos vinculados del teléfono, o si el teléfono pasó unos 14 días sin internet. Abrí `2-iniciar` y repetí el paso 3.

**El bot no contesta.** Revisá:
- Que la ventana del bot esté abierta y diga "Conectado a WhatsApp".
- Que le estés escribiendo desde **otro** número, no desde el número del bot.
- Que el texto sea exactamente `.sticker`, con el punto adelante.
- Que el video dure 10 segundos o menos.
- Si nada de eso es, mirá qué dice la ventana o el archivo `data\bot.log`.

**Dice "Ya hay otra ventana de Licha.bot abierta".**
Cerrá las ventanas que sobran. Fijate en la barra de tareas: si hiciste el paso 5, puede haber una minimizada.

**Contesta "No pude descargar el archivo".**
La foto o el video son viejos y WhatsApp ya no los tiene. Mandalos de nuevo.

---

## Importante

- **El archivo `C:\LichaBot\data\session.sqlite3` es como la llave de ese WhatsApp.** Quien lo tenga puede usarlo. No lo compartas ni lo subas a ningún lado.
- **Para pasar el bot a otra PC:** instalalo en la nueva desde el paso 1. Después apagá el bot en la vieja, copiá la carpeta `data` de la vieja a la nueva y no lo prendas más en la vieja.
- **Para desinstalarlo:**
  1. Desactivá el inicio automático (paso 5).
  2. Cerrá el bot.
  3. En el teléfono, quitá "Licha.bot" de los dispositivos vinculados.
  4. Borrá la carpeta `C:\LichaBot`.

  Python y ffmpeg se pueden desinstalar desde Configuración > Aplicaciones.

¿Querés que el bot arranque aunque nadie inicie sesión, o usarlo con Docker? Eso está en el `README.md`, sección "Dejarlo corriendo 24/7".
