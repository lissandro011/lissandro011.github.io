"""PLANTILLA PARA CREAR COMANDOS NUEVOS (este archivo no se carga).

Los archivos que empiezan con "_" se ignoran. Para usar esta plantilla:

  1. Copiá este archivo en la misma carpeta con otro nombre, SIN el "_" de
     adelante. Por ejemplo: comandos\\diversion.py
  2. Cambiá o borrá los ejemplos de abajo.
  3. Reiniciá el bot: cerrá la ventana y abrí iniciar.bat, o, si tu número
     está en "duenos" de config.toml, mandale !reiniciar por WhatsApp.
  4. Escribile !menu: tus comandos aparecen solos en la lista.

Si un archivo tiene un error, el bot arranca igual con los demás comandos y el
error queda en logs\\licha-bot.log.

Lo que podés usar dentro de un comando (ctx):

  ctx.args          palabras después del comando: "!dado 20" -> ["20"]
  ctx.texto_args    todo lo de después del comando, como texto
  ctx.nombre        nombre de quien escribió
  ctx.numero        su número (si WhatsApp lo informa)
  ctx.es_grupo      True si es un grupo
  ctx.es_dueno      True si su número está en "duenos"
  ctx.prefijo       el prefijo que usó ("!" o ".")
  ctx.config        la configuración (ctx.config.seccion("mi_seccion") lee
                    una sección propia de config.toml)

  await ctx.responder("texto")           responde citando el mensaje
  await ctx.enviar("texto")              manda un mensaje sin citar
  await ctx.reaccionar("👍")             reacciona al mensaje
  ctx.media()                            foto/video/sticker del mensaje o
                                         del mensaje respondido (o None)
  await ctx.descargar(media)             bytes de esa foto/video/sticker
  await ctx.enviar_imagen(jpeg, "pie")   manda una foto
  await ctx.enviar_sticker(webp)         manda un sticker
  await ctx.en_segundo_plano(f, ...)     corre algo lento sin trabar al bot

  raise ErrorUsuario("mensaje")          corta el comando y responde ese mensaje

Opciones de @comando: alias (los nombres extra después del primero),
descripcion, uso ("{p}" se cambia por el prefijo), categoria, solo_grupos,
solo_privado, solo_dueno y oculto (no aparece en el menú).
"""

from __future__ import annotations

import io
import random

from PIL import Image

from licha_bot import ErrorUsuario, comando
from licha_bot.contexto import Contexto

# --------------------------------------------------------------------------- #
# Ejemplo 1: un comando simple con un argumento opcional.
#   !dado      -> número del 1 al 6
#   !dado 20   -> número del 1 al 20
# --------------------------------------------------------------------------- #


@comando(
    "dado", "dados",
    categoria="Diversión",
    descripcion="Tira un dado",
    uso="{p}dado → del 1 al 6\n{p}dado 20 → del 1 al 20",
)  # fmt: skip
async def dado(ctx: Contexto) -> None:
    caras = 6
    if ctx.args:
        if not ctx.args[0].isdigit() or not 2 <= int(ctx.args[0]) <= 1000:
            raise ErrorUsuario(f"Decime un número de caras entre 2 y 1000. Ejemplo: {ctx.prefijo}dado 20")
        caras = int(ctx.args[0])
    await ctx.responder(f"🎲 Salió {random.randint(1, caras)}")


# --------------------------------------------------------------------------- #
# Ejemplo 2: usar todo el texto y una sección propia de config.toml.
# En config.toml podés agregar al final:
#
#   [eco]
#   emoji = "🦜"
# --------------------------------------------------------------------------- #


@comando("eco", "repetir", categoria="Diversión", descripcion="Repite lo que le digas", uso="{p}eco hola mundo")
async def eco(ctx: Contexto) -> None:
    if not ctx.texto_args:
        raise ErrorUsuario(ctx.uso())
    emoji = ctx.config.seccion("eco").get("emoji", "🦜")
    await ctx.responder(f"{emoji} {ctx.texto_args}")


# --------------------------------------------------------------------------- #
# Ejemplo 3: trabajar con una foto (girarla) y devolverla.
# Lo pesado va en una función normal que se corre con ctx.en_segundo_plano.
# --------------------------------------------------------------------------- #


def girar_foto(datos: bytes) -> bytes:
    with Image.open(io.BytesIO(datos)) as img:
        girada = img.convert("RGB").rotate(-90, expand=True)
    salida = io.BytesIO()
    girada.save(salida, format="JPEG", quality=90)
    return salida.getvalue()


@comando("girar", categoria="Diversión", descripcion="Gira una foto", uso="Respondé a una foto con {p}girar")
async def girar(ctx: Contexto) -> None:
    media = ctx.media()
    if media is None or media.tipo != "imagen":
        raise ErrorUsuario(ctx.uso())
    datos = await ctx.descargar(media)
    resultado = await ctx.en_segundo_plano(girar_foto, datos)
    await ctx.enviar_imagen(resultado)


# --------------------------------------------------------------------------- #
# Ejemplo 4: un comando solo para grupos y solo para los dueños.
# --------------------------------------------------------------------------- #


@comando("anuncio", categoria="Dueño", descripcion="Manda un anuncio al grupo", solo_grupos=True, solo_dueno=True)
async def anuncio(ctx: Contexto) -> None:
    if not ctx.texto_args:
        raise ErrorUsuario(f"Escribí el anuncio después del comando: {ctx.prefijo}anuncio Mañana no hay clases")
    await ctx.enviar(f"📢 *Anuncio*\n{ctx.texto_args}")
