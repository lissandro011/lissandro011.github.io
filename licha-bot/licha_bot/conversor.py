"""Conversión de fotos, videos y GIFs a stickers de WhatsApp.

Este módulo no sabe nada de WhatsApp: recibe bytes y devuelve un WebP listo
para mandar. Solo usa Pillow y PyAV (que ya trae FFmpeg adentro), así que en
Windows no hace falta instalar ningún programa aparte.

- Foto -> sticker estático de 512x512, menos de 100 KB.
- Video, GIF o sticker animado -> sticker animado de 512x512, menos de 500 KB
  y hasta 10 segundos (si el video es más largo se usan los primeros 10 s).

Se mantiene la proporción con fondo transparente (o se recorta al centro con
`recortar=True`) y se guardan los metadatos que WhatsApp muestra como nombre
del paquete y autor.

Para probarlo sin WhatsApp:

    python -m licha_bot.conversor foto.jpg sticker.webp
    python -m licha_bot.conversor video.mp4 sticker.webp --recortar
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import math
import struct
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageSequence, UnidentifiedImageError

from .errores import ErrorUsuario

log = logging.getLogger("licha.conversor")

LIENZO = 512  # WhatsApp pide stickers de 512x512
FPS_MAX = 15
DURACION_GIF_POR_DEFECTO_MS = 100  # GIFs con duración 0 o ausente (los navegadores usan 100 ms)

# Intentos para stickers animados: (cuadros por segundo, calidad, lado del contenido).
# Se prueban en orden hasta que el archivo entra en el peso máximo. Si un intento
# queda muy lejos del objetivo se saltan escalones.
ESCALERA_ANIMADO: tuple[tuple[int, int, int], ...] = (
    (15, 75, 512),
    (15, 55, 512),
    (12, 45, 512),
    (10, 35, 512),
    (10, 25, 448),
    (8, 20, 384),
    (8, 12, 320),
    (6, 10, 256),
)
LADOS_ESTATICO = (512, 448, 384, 320, 256)


class ErrorSticker(ErrorUsuario):
    """No se pudo hacer el sticker; `mensaje` se le muestra a quien lo pidió."""


@dataclass(frozen=True)
class OpcionesSticker:
    paquete: str = "Licha Bot"
    autor: str = "Licha Bot"
    marca_de_agua: str = ""  # texto visible en una esquina ("" = sin marca)
    recortar: bool = False  # True: recorta al centro y llena el cuadrado
    max_bytes_estatico: int = 100 * 1024
    max_bytes_animado: int = 500 * 1024
    max_segundos: float = 10.0


OPCIONES_POR_DEFECTO = OpcionesSticker()


@dataclass(frozen=True)
class Sticker:
    datos: bytes
    animado: bool


# --------------------------------------------------------------------------- #
# Metadatos (nombre del paquete y autor)
# --------------------------------------------------------------------------- #


def construir_exif(paquete: str, autor: str, id_paquete: str = "lichabot.stickers") -> bytes:
    """EXIF que WhatsApp lee para mostrar el paquete y el autor del sticker.

    Es una cabecera TIFF little-endian con una sola entrada (tag 0x5741, tipo
    UNDEFINED) que apunta a un JSON ubicado en el byte 22. Es el formato que
    usan neonize y wa-sticker-formatter.
    """
    carga = json.dumps(
        {
            "sticker-pack-id": id_paquete,
            "sticker-pack-name": paquete,
            "sticker-pack-publisher": autor,
            "emojis": [""],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    cabecera = bytearray.fromhex("49 49 2A 00 08 00 00 00 01 00 41 57 07 00 00 00 00 00 16 00 00 00")
    cabecera[14:18] = len(carga).to_bytes(4, "little")
    return bytes(cabecera) + carga


def chunks_webp(datos: bytes) -> Iterator[tuple[bytes, bytes]]:
    """Recorre los bloques RIFF de un WebP: (tipo, contenido)."""
    if len(datos) < 12 or datos[:4] != b"RIFF" or datos[8:12] != b"WEBP":
        raise ValueError("no es un archivo WebP")
    pos = 12
    while pos + 8 <= len(datos):
        tipo = datos[pos : pos + 4]
        (largo,) = struct.unpack("<I", datos[pos + 4 : pos + 8])
        inicio = pos + 8
        yield tipo, datos[inicio : inicio + largo]
        pos = inicio + largo + (largo & 1)  # los bloques se rellenan a tamaño par


def inspeccionar_webp(datos: bytes) -> dict:
    """Tamaño, cuadros y metadatos de un sticker (para pruebas y la consola)."""
    exif = None
    for tipo, contenido in chunks_webp(datos):
        if tipo == b"EXIF" and len(contenido) > 22:
            exif = json.loads(contenido[22:].decode("utf-8"))
    with Image.open(io.BytesIO(datos)) as img:
        return {
            "bytes": len(datos),
            "ancho": img.width,
            "alto": img.height,
            "cuadros": getattr(img, "n_frames", 1),
            "animado": bool(getattr(img, "is_animated", False)),
            "duracion_ms": _duracion_total_ms(img),
            "exif": exif,
        }


def _duracion_total_ms(img: Image.Image) -> int:
    total = 0
    for cuadro in ImageSequence.Iterator(img):
        cuadro.load()  # en WebP la duración del cuadro se lee recién al cargarlo
        total += int(cuadro.info.get("duration", 0) or 0)
    img.seek(0)
    return total


# --------------------------------------------------------------------------- #
# Encuadre y marca de agua
# --------------------------------------------------------------------------- #


def medida_contenida(ancho: int, alto: int, lado: int = LIENZO) -> tuple[int, int]:
    """Tamaño que entra en un cuadrado de `lado` manteniendo la proporción."""
    escala = min(lado / ancho, lado / alto)
    return max(1, round(ancho * escala)), max(1, round(alto * escala))


Caja = tuple[int, int, int, int]  # x0, y0, x1, y1 del contenido dentro del lienzo


def encuadrar(img: Image.Image, recortar: bool) -> tuple[Image.Image, Caja]:
    """Pone la imagen en un lienzo transparente de 512x512.

    Sin recortar entra completa (con bordes transparentes); recortando se
    corta al centro y llena todo el cuadrado.
    """
    img = img.convert("RGBA")
    if recortar:
        img = ImageOps.fit(img, (LIENZO, LIENZO), Image.Resampling.LANCZOS)
    else:
        img = img.resize(medida_contenida(*img.size), Image.Resampling.LANCZOS)
    x, y = (LIENZO - img.width) // 2, (LIENZO - img.height) // 2
    lienzo = Image.new("RGBA", (LIENZO, LIENZO), (0, 0, 0, 0))
    lienzo.alpha_composite(img, (x, y))
    return lienzo, (x, y, x + img.width, y + img.height)


def _fuente(tamano: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size=tamano)  # Pillow >= 10.1: fuente escalable incluida
    except (TypeError, OSError):
        return ImageFont.load_default()


def dibujar_marca(texto: str, ancho_max: int, tamano: int = 24) -> Image.Image:
    """Texto blanco con borde oscuro sobre fondo transparente, recortado al contenido.

    Achica la letra hasta que entre en `ancho_max` (mínimo 10 px).
    """
    sonda = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    while True:
        fuente = _fuente(tamano)
        borde = max(1, round(tamano / 10))
        izq, arr, der, aba = sonda.textbbox((0, 0), texto, font=fuente, stroke_width=borde)
        if der - izq <= ancho_max or tamano <= 10:
            break
        tamano -= 2
    margen = 2
    marca = Image.new("RGBA", (der - izq + 2 * margen, aba - arr + 2 * margen), (0, 0, 0, 0))
    ImageDraw.Draw(marca).text(
        (margen - izq, margen - arr),
        texto,
        font=fuente,
        fill=(255, 255, 255, 235),
        stroke_width=borde,
        stroke_fill=(0, 0, 0, 190),
    )
    return marca


def preparar_marca(texto: str, caja: Caja) -> tuple[Image.Image, tuple[int, int]] | None:
    """Marca de agua y su posición (esquina inferior derecha del contenido)."""
    if not texto:
        return None
    x0, y0, x1, y1 = caja
    ancho, alto = x1 - x0, y1 - y0
    margen = max(4, round(min(ancho, alto) * 0.025))
    marca = dibujar_marca(texto, ancho_max=max(20, int(ancho * 0.6) - 2 * margen))
    return marca, (max(x0, x1 - marca.width - margen), max(y0, y1 - marca.height - margen))


def _achicar(lienzo: Image.Image, lado: int) -> Image.Image:
    """Achica el contenido a `lado` y lo centra en un lienzo de 512 (pesa menos)."""
    if lado >= LIENZO:
        return lienzo
    chico = lienzo.resize((lado, lado), Image.Resampling.LANCZOS)
    nuevo = Image.new("RGBA", (LIENZO, LIENZO), (0, 0, 0, 0))
    nuevo.alpha_composite(chico, ((LIENZO - lado) // 2, (LIENZO - lado) // 2))
    return nuevo


# --------------------------------------------------------------------------- #
# Codificación
# --------------------------------------------------------------------------- #


def _mayor_calidad_bajo(codificar: Callable[[int], bytes], max_bytes: int, minima: int, maxima: int) -> bytes:
    """Búsqueda binaria de la mayor calidad cuyo resultado pesa <= max_bytes.

    Prueba primero la calidad máxima (el caso común). Si ni la mínima entra,
    devuelve el resultado más liviano.
    """
    primero = codificar(maxima)
    if len(primero) <= max_bytes:
        return primero
    mejor: bytes | None = None
    mas_liviano = primero
    bajo, alto = minima, maxima - 1
    while bajo <= alto:
        calidad = (bajo + alto) // 2
        salida = codificar(calidad)
        if len(salida) < len(mas_liviano):
            mas_liviano = salida
        if len(salida) <= max_bytes:
            mejor, bajo = salida, calidad + 1
        else:
            alto = calidad - 1
    return mejor if mejor is not None else mas_liviano


def codificar_estatico(lienzo: Image.Image, exif: bytes, max_bytes: int) -> bytes:
    """WebP estático de la mayor calidad que entra en `max_bytes`."""
    salida = b""
    for lado in LADOS_ESTATICO:
        imagen = _achicar(lienzo, lado)

        def codificar(calidad: int, imagen: Image.Image = imagen) -> bytes:
            buf = io.BytesIO()
            # method=6 comprime apenas mejor pero tarda mucho más con transparencias.
            imagen.save(buf, format="WEBP", quality=calidad, method=4, exif=exif)
            return buf.getvalue()

        salida = _mayor_calidad_bajo(codificar, max_bytes, minima=5, maxima=92)
        if len(salida) <= max_bytes:
            return salida
    log.warning("El sticker estático pesa %d bytes y supera el objetivo de %d", len(salida), max_bytes)
    return salida


def codificar_animado(cuadros: list[Image.Image], duraciones_ms: list[int], calidad: int, exif: bytes) -> bytes:
    buf = io.BytesIO()
    cuadros[0].save(
        buf,
        format="WEBP",
        save_all=True,
        append_images=cuadros[1:],
        duration=duraciones_ms,
        loop=0,
        quality=calidad,
        method=4,
        background=(0, 0, 0, 0),  # fondo transparente
        exif=exif,
    )
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Lectura de cuadros
# --------------------------------------------------------------------------- #

Cuadro = tuple[Image.Image, float]  # (lienzo 512x512 RGBA, segundo en que empieza)


def _abrir_imagen(datos: bytes) -> Image.Image | None:
    """Abre los datos con Pillow; None si no es una imagen (por ejemplo, un video)."""
    try:
        img = Image.open(io.BytesIO(datos))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        return None
    return img


def _toca_un_tic(inicio: float, fin: float, paso: float) -> bool:
    """True si en [inicio, fin) cae algún múltiplo de `paso` (un cuadro a FPS_MAX)."""
    proximo = math.ceil(inicio / paso - 1e-9) * paso
    return proximo < fin - 1e-9


def cuadros_de_imagen_animada(img: Image.Image, opciones: OpcionesSticker) -> tuple[list[Cuadro], float, Caja]:
    """Cuadros de un GIF o WebP animado (Pillow ya resuelve la composición entre cuadros)."""
    paso = 1 / FPS_MAX
    cuadros: list[Cuadro] = []
    caja: Caja = (0, 0, LIENZO, LIENZO)
    t = 0.0
    for cuadro in ImageSequence.Iterator(img):
        if t >= opciones.max_segundos:
            break
        cuadro.load()  # en WebP la duración del cuadro se lee recién al cargarlo
        duracion = (cuadro.info.get("duration") or DURACION_GIF_POR_DEFECTO_MS) / 1000
        # Solo guardamos los cuadros que se verían a 15 fps: así un GIF de 500
        # cuadros no llena la memoria.
        if not cuadros or _toca_un_tic(t, t + duracion, paso):
            lienzo, caja = encuadrar(cuadro, opciones.recortar)
            cuadros.append((lienzo, t))
        t += duracion
    return cuadros, min(t, opciones.max_segundos), caja


def cuadros_de_video(datos: bytes, opciones: OpcionesSticker) -> tuple[list[Cuadro], float, Caja]:
    """Cuadros de un video (MP4, los "GIF" de WhatsApp, WebM, ...) usando PyAV."""
    try:
        import av
    except ImportError as exc:
        raise ErrorSticker("El bot no puede procesar videos ahora.", "Falta PyAV: pip install av") from exc

    try:
        contenedor = av.open(io.BytesIO(datos))
    except Exception as exc:  # PyAV lanza distintos errores según el formato
        raise ErrorSticker("No pude leer el archivo (¿es una foto, un video o un GIF?).", f"PyAV: {exc!r}") from exc

    paso = 1 / FPS_MAX
    cuadros: list[Cuadro] = []
    caja: Caja = (0, 0, LIENZO, LIENZO)
    with contenedor:
        if not contenedor.streams.video:
            raise ErrorSticker("Ese archivo no tiene imagen.", "sin pistas de video")
        pista = contenedor.streams.video[0]
        pista.thread_type = "AUTO"
        ultimo = -1.0
        proximo = 0.0
        try:
            for frame in contenedor.decode(pista):
                t = frame.time if frame.time is not None else ultimo + paso
                if t >= opciones.max_segundos:
                    break
                ultimo = max(t, 0.0)
                if cuadros and t + 1e-6 < proximo:
                    continue  # más cuadros por segundo de los que usamos
                proximo = (math.floor(t / paso + 1e-6) + 1) * paso
                img = frame.to_image()
                rotacion = getattr(frame, "rotation", 0) or 0
                if rotacion % 360:  # videos de celular grabados en vertical
                    img = img.rotate(rotacion, expand=True)
                lienzo, caja = encuadrar(img, opciones.recortar)
                cuadros.append((lienzo, max(t, 0.0)))
        except Exception as exc:
            if not cuadros:
                raise ErrorSticker("No pude leer el video.", f"PyAV al decodificar: {exc!r}") from exc
            log.warning("El video se cortó a la mitad (%r); uso los cuadros que se pudieron leer", exc)

        if not cuadros:
            raise ErrorSticker("No pude leer el video.", "el video no tiene cuadros")

        duracion = None
        if pista.duration and pista.time_base:
            duracion = float(pista.duration * pista.time_base)
        elif contenedor.duration:
            duracion = contenedor.duration / av.time_base
        # Por si los metadatos mienten: al menos hasta el último cuadro leído.
        duracion = max(duracion or 0.0, ultimo + paso)
    return cuadros, min(duracion, opciones.max_segundos), caja


def remuestrear(cuadros: list[Cuadro], duracion: float, fps: int) -> list[tuple[Image.Image, int]]:
    """Elige los cuadros a mostrar a `fps` y la duración de cada uno en ms.

    Si un mismo cuadro cubre varios instantes seguidos (un GIF lento, una toma
    quieta) se manda una sola vez con más duración: pesa mucho menos.
    """
    paso = 1 / fps
    total = max(1, math.ceil(duracion * fps - 1e-6))
    elegidos: list[tuple[int, int]] = []  # (índice del cuadro, inicio en ms)
    j = 0
    for k in range(total):
        t = k * paso
        while j + 1 < len(cuadros) and cuadros[j + 1][1] <= t + 1e-6:
            j += 1
        if elegidos and elegidos[-1][0] == j:
            continue
        elegidos.append((j, round(t * 1000)))
    fin_ms = max(round(duracion * 1000), elegidos[-1][1] + 10)
    salida = []
    for i, (j, inicio) in enumerate(elegidos):
        fin = elegidos[i + 1][1] if i + 1 < len(elegidos) else fin_ms
        salida.append((cuadros[j][0], max(10, fin - inicio)))
    return salida


# --------------------------------------------------------------------------- #
# API principal
# --------------------------------------------------------------------------- #


def crear_sticker(datos: bytes, opciones: OpcionesSticker = OPCIONES_POR_DEFECTO) -> Sticker:
    """Convierte una foto, video, GIF o sticker en un sticker de WhatsApp."""
    exif = construir_exif(opciones.paquete, opciones.autor)
    img = _abrir_imagen(datos)
    if img is not None:
        with img:
            if getattr(img, "n_frames", 1) <= 1:
                return Sticker(_sticker_estatico(img, opciones, exif), animado=False)
            cuadros, duracion, caja = cuadros_de_imagen_animada(img, opciones)
    else:
        cuadros, duracion, caja = cuadros_de_video(datos, opciones)
    return _sticker_animado(cuadros, duracion, caja, opciones, exif)


def _sticker_estatico(img: Image.Image, opciones: OpcionesSticker, exif: bytes) -> bytes:
    try:
        img = ImageOps.exif_transpose(img)  # fotos de celular giradas
    except (OSError, ValueError) as exc:
        raise ErrorSticker("No pude leer la imagen.", f"Pillow: {exc!r}") from exc
    lienzo, caja = encuadrar(img, opciones.recortar)
    marca = preparar_marca(opciones.marca_de_agua, caja)
    if marca:
        lienzo.alpha_composite(*marca)
    return codificar_estatico(lienzo, exif, opciones.max_bytes_estatico)


def _sticker_animado(
    cuadros: list[Cuadro], duracion: float, caja: Caja, opciones: OpcionesSticker, exif: bytes
) -> Sticker:
    marca = preparar_marca(opciones.marca_de_agua, caja)
    if marca:
        for lienzo, _ in cuadros:
            lienzo.alpha_composite(*marca)

    if len(cuadros) == 1:  # un "video" de un solo cuadro es una foto
        return Sticker(codificar_estatico(cuadros[0][0], exif, opciones.max_bytes_estatico), animado=False)

    presupuesto = opciones.max_bytes_animado
    mejor: bytes | None = None
    intento = 0
    while intento < len(ESCALERA_ANIMADO):
        fps, calidad, lado = ESCALERA_ANIMADO[intento]
        elegidos = remuestrear(cuadros, duracion, fps)
        if len(elegidos) == 1:
            return Sticker(codificar_estatico(elegidos[0][0], exif, opciones.max_bytes_estatico), animado=False)
        imagenes = [_achicar(lienzo, lado) for lienzo, _ in elegidos]
        salida = codificar_animado(imagenes, [ms for _, ms in elegidos], calidad, exif)
        log.debug("Intento %d (fps=%d calidad=%d lado=%d): %d bytes", intento, fps, calidad, lado, len(salida))
        if mejor is None or len(salida) < len(mejor):
            mejor = salida
        if len(salida) <= presupuesto:
            break
        # Cuanto más lejos del objetivo, más escalones saltamos (cada intento tarda).
        proporcion = len(salida) / presupuesto
        intento += 1 if proporcion <= 1.5 else 2 if proporcion <= 3 else 3

    assert mejor is not None
    if len(mejor) > presupuesto:
        log.warning("El sticker animado pesa %d bytes y supera el objetivo de %d", len(mejor), presupuesto)
    return Sticker(mejor, animado=True)


def sticker_a_imagen(datos: bytes) -> tuple[bytes, bool]:
    """Convierte un sticker (o cualquier imagen) en JPEG con fondo blanco.

    Devuelve (jpeg, era_animado). De los animados se usa el primer cuadro.
    """
    img = _abrir_imagen(datos)
    if img is None:
        raise ErrorSticker("No pude leer ese sticker.", "Pillow no pudo abrir el sticker")
    with img:
        animado = getattr(img, "n_frames", 1) > 1
        img.seek(0)
        rgba = img.convert("RGBA")
    fondo = Image.new("RGB", rgba.size, (255, 255, 255))
    fondo.paste(rgba, mask=rgba.getchannel("A"))
    buf = io.BytesIO()
    fondo.save(buf, format="JPEG", quality=92)
    return buf.getvalue(), animado


def miniatura_jpeg(datos: bytes, lado: int = 96) -> tuple[bytes, int, int]:
    """Miniatura JPEG (para la vista previa de las fotos) y medidas de la imagen original."""
    with Image.open(io.BytesIO(datos)) as img:
        ancho, alto = img.size
        img.thumbnail((lado, lado))
        rgb = img.convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=70)
    return buf.getvalue(), ancho, alto


# --------------------------------------------------------------------------- #
# Uso por consola
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convierte una foto, video o GIF en sticker de WhatsApp.")
    parser.add_argument("entrada", type=Path)
    parser.add_argument("salida", type=Path)
    parser.add_argument("--recortar", action="store_true", help="recorta al centro en vez de dejar bordes")
    parser.add_argument("--marca", default="", help="texto visible en la esquina")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")

    opciones = OpcionesSticker(marca_de_agua=args.marca, recortar=args.recortar)
    try:
        sticker = crear_sticker(args.entrada.read_bytes(), opciones)
    except ErrorSticker as exc:
        print(f"Error: {exc.mensaje} ({exc})", file=sys.stderr)
        return 1
    args.salida.write_bytes(sticker.datos)
    print(json.dumps(inspeccionar_webp(sticker.datos), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
