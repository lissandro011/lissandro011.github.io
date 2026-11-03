"""Conversión de imágenes y videos a stickers de WhatsApp.

Este módulo no depende de neonize ni de WhatsApp: recibe bytes y devuelve
bytes WebP listos para mandar, así que se puede probar en cualquier máquina
con Pillow y ffmpeg.

- Imágenes -> WebP estático 512x512 (Pillow), objetivo < 100 KB.
- Videos/GIF -> WebP animado 512x512 (ffmpeg + libwebp), objetivo < 500 KB.

En ambos casos se mantiene la proporción con fondo transparente, se dibuja la
marca de agua (por defecto "Licha.bot") y se incrustan los metadatos EXIF que
WhatsApp muestra como nombre del paquete y autor del sticker.

Uso por línea de comandos (para probar sin WhatsApp):

    python sticker.py foto.jpg salida.webp
    python sticker.py video.mp4 salida.webp
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import shutil
import struct
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

log = logging.getLogger(__name__)

CANVAS = 512
# Si el video dice durar hasta medio segundo más que el máximo lo aceptamos y lo
# recortamos: WhatsApp muestra "0:10" para un video de 10,4 s.
DURATION_TOLERANCE = 0.5

# Escalera de intentos para stickers animados: (fps, calidad, lado del contenido).
# Se prueba en orden hasta que el archivo entra en el tamaño objetivo.
# Cuando un intento queda muy lejos del objetivo se saltan escalones.
ANIMATED_LADDER: tuple[tuple[int, int, int], ...] = (
    (15, 70, 512),
    (15, 50, 512),
    (12, 40, 512),
    (10, 30, 512),
    (10, 20, 448),
    (8, 15, 384),
    (8, 10, 320),
)


class StickerError(Exception):
    """Error esperado, con un mensaje corto para mostrarle al usuario.

    `user_message` es lo que se responde en el chat; el texto de la excepción
    (detalle técnico) es lo que va al log.
    """

    def __init__(self, user_message: str, detail: str | None = None):
        super().__init__(detail or user_message)
        self.user_message = user_message


@dataclass(frozen=True)
class StickerOptions:
    pack_name: str = "Licha.bot"
    publisher: str = "Licha.bot"
    watermark: str = "Licha.bot"  # "" desactiva la marca visible
    image_max_bytes: int = 100 * 1024
    animated_max_bytes: int = 500 * 1024
    max_video_seconds: float = 10.0
    ffmpeg_timeout: float = 120.0


DEFAULT_OPTIONS = StickerOptions()


# --------------------------------------------------------------------------- #
# Metadatos EXIF (nombre del paquete / autor)
# --------------------------------------------------------------------------- #


def build_exif(pack_name: str, publisher: str, pack_id: str = "bot.licha.stickers") -> bytes:
    """EXIF que WhatsApp lee para mostrar paquete y autor del sticker.

    Es el mismo formato que usan neonize y wa-sticker-formatter: cabecera TIFF
    little-endian con una sola entrada (tag 0x5741, tipo UNDEFINED) que apunta
    a un JSON ubicado en el offset 22.
    """
    payload = json.dumps(
        {
            "sticker-pack-id": pack_id,
            "sticker-pack-name": pack_name,
            "sticker-pack-publisher": publisher,
            "emojis": [""],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    header = bytearray.fromhex("49 49 2A 00 08 00 00 00 01 00 41 57 07 00 00 00 00 00 16 00 00 00")
    header[14:18] = len(payload).to_bytes(4, "little")
    return bytes(header) + payload


def iter_webp_chunks(data: bytes) -> Iterator[tuple[bytes, bytes]]:
    """Recorre los chunks RIFF de un WebP y devuelve (fourcc, contenido)."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("no es un archivo WebP")
    pos = 12
    while pos + 8 <= len(data):
        fourcc = data[pos : pos + 4]
        (size,) = struct.unpack("<I", data[pos + 4 : pos + 8])
        start = pos + 8
        yield fourcc, data[start : start + size]
        pos = start + size + (size & 1)  # los chunks se rellenan a tamaño par


VP8X_ALPHA = 0x10
VP8X_EXIF = 0x08


def add_exif_to_webp(data: bytes, exif: bytes) -> bytes:
    """Inserta (o reemplaza) el chunk EXIF en un WebP extendido (VP8X).

    ffmpeg no escribe EXIF, así que lo agregamos a mano sin recomprimir.

    De paso corrige dos cosas de la salida de ffmpeg que rompen la
    transparencia: libwebp guarda cuadros recortados al área con contenido y,
    con un solo cuadro, no activa la bandera de alpha (el resto del lienzo se ve
    negro); además deja el color de fondo de la animación en blanco opaco.
    """
    chunks = list(iter_webp_chunks(data))
    if not chunks or chunks[0][0] != b"VP8X":
        raise ValueError("el WebP no tiene cabecera VP8X")
    vp8x = bytearray(chunks[0][1])
    vp8x[0] |= VP8X_EXIF | VP8X_ALPHA
    fixed: list[tuple[bytes, bytes]] = [(b"VP8X", bytes(vp8x))]
    for fourcc, payload in chunks[1:]:
        if fourcc == b"EXIF":
            continue
        if fourcc == b"ANIM" and len(payload) >= 4:
            payload = b"\x00\x00\x00\x00" + payload[4:]  # fondo transparente (BGRA)
        fixed.append((fourcc, payload))
    chunks = fixed
    # Según la especificación, EXIF va después de los frames y antes de XMP.
    xmp_at = next((i for i, (fourcc, _) in enumerate(chunks) if fourcc == b"XMP "), len(chunks))
    chunks.insert(xmp_at, (b"EXIF", exif))

    body = bytearray(b"WEBP")
    for fourcc, payload in chunks:
        body += fourcc + struct.pack("<I", len(payload)) + payload
        if len(payload) & 1:
            body += b"\x00"
    return b"RIFF" + struct.pack("<I", len(body)) + bytes(body)


# --------------------------------------------------------------------------- #
# Marca de agua
# --------------------------------------------------------------------------- #


def _load_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1 (fuente escalable)
    except (TypeError, OSError):  # Pillow viejo o sin FreeType
        return ImageFont.load_default()


def render_watermark(text: str, max_width: int, font_size: int = 24) -> Image.Image:
    """Texto blanco con borde oscuro sobre fondo transparente, recortado al contenido.

    Se achica la letra hasta que entre en `max_width` (mínimo 10 px).
    """
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    while True:
        font = _load_font(font_size)
        stroke = max(1, round(font_size / 10))
        left, top, right, bottom = probe.textbbox((0, 0), text, font=font, stroke_width=stroke)
        if right - left <= max_width or font_size <= 10:
            break
        font_size -= 2
    pad = 2
    mark = Image.new("RGBA", (right - left + 2 * pad, bottom - top + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(mark).text(
        (pad - left, pad - top),
        text,
        font=font,
        fill=(255, 255, 255, 235),
        stroke_width=stroke,
        stroke_fill=(0, 0, 0, 190),
    )
    return mark


def _watermark_margin(content_w: int, content_h: int) -> int:
    return max(4, round(min(content_w, content_h) * 0.025))


def _watermark_for(text: str, content_w: int, content_h: int) -> tuple[Image.Image, int]:
    margin = _watermark_margin(content_w, content_h)
    mark = render_watermark(text, max_width=max(20, int(content_w * 0.6) - 2 * margin))
    return mark, margin


# --------------------------------------------------------------------------- #
# Imágenes -> sticker estático
# --------------------------------------------------------------------------- #


def fit_size(width: int, height: int, side: int = CANVAS) -> tuple[int, int]:
    """Tamaño que entra en un cuadrado `side`x`side` manteniendo la proporción."""
    scale = min(side / width, side / height)
    return max(1, round(width * scale)), max(1, round(height * scale))


def _highest_quality_under(encode: Callable[[int], bytes], max_bytes: int, lo: int, hi: int) -> bytes:
    """Búsqueda binaria de la mayor calidad cuyo resultado pesa <= max_bytes.

    Primero prueba la calidad máxima (el caso común: entra de una). Si ni la
    calidad mínima entra, devuelve el resultado más chico.
    """
    first = encode(hi)
    if len(first) <= max_bytes:
        return first
    best: bytes | None = None
    smallest: bytes | None = first
    hi -= 1
    while lo <= hi:
        q = (lo + hi) // 2
        out = encode(q)
        if smallest is None or len(out) < len(smallest):
            smallest = out
        if len(out) <= max_bytes:
            best, lo = out, q + 1
        else:
            hi = q - 1
    return best if best is not None else smallest  # type: ignore[return-value]


def image_to_sticker(data: bytes, opts: StickerOptions = DEFAULT_OPTIONS) -> bytes:
    """Convierte una imagen (JPEG, PNG, WebP, ...) en un sticker WebP estático."""
    try:
        with Image.open(io.BytesIO(data)) as src:
            if src.format == "JPEG":
                src.draft("RGB", (CANVAS, CANVAS))  # decodifica fotos enormes más rápido
            src.seek(0)  # en GIF/WebP animados usamos el primer cuadro
            img = ImageOps.exif_transpose(src).convert("RGBA")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise StickerError("No pude leer la imagen.", f"Pillow no pudo abrir la imagen: {exc!r}") from exc

    w, h = fit_size(*img.size)
    img = img.resize((w, h), Image.Resampling.LANCZOS)
    x, y = (CANVAS - w) // 2, (CANVAS - h) // 2

    if opts.watermark:
        mark, margin = _watermark_for(opts.watermark, w, h)
        img.alpha_composite(mark, (max(0, w - mark.width - margin), max(0, h - mark.height - margin)))

    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    canvas.alpha_composite(img, (x, y))
    return _encode_static(canvas, build_exif(opts.pack_name, opts.publisher), opts.image_max_bytes)


def _encode_static(canvas: Image.Image, exif: bytes, max_bytes: int) -> bytes:
    def encode(quality: int) -> bytes:
        buf = io.BytesIO()
        # method=6 comprime apenas mejor pero tarda ~50 veces más con transparencias.
        canvas.save(buf, format="WEBP", quality=quality, method=4, exif=exif)
        return buf.getvalue()

    out = _highest_quality_under(encode, max_bytes, lo=5, hi=92)
    if len(out) > max_bytes:
        log.warning("Sticker estático de %d bytes supera el objetivo de %d", len(out), max_bytes)
    return out


# --------------------------------------------------------------------------- #
# Videos / GIF -> sticker animado
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class VideoInfo:
    duration: float
    width: int
    height: int


def _require(binary: str) -> str:
    path = shutil.which(binary)
    if path is None:
        raise StickerError("El bot no puede procesar videos ahora.", f"No se encontró '{binary}' en el PATH")
    return path


def probe_video(path: Path, timeout: float = 30.0) -> VideoInfo:
    """Duración y tamaño visible (ya rotado) del primer stream de video."""
    cmd = [
        _require("ffprobe"),
        "-v", "error",
        "-select_streams", "v:0",
        # JSON completo en vez de -show_entries: los nombres de secciones cambian entre versiones.
        "-show_format", "-show_streams",
        "-of", "json",
        str(path),
    ]  # fmt: skip
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise StickerError("No pude leer el video.", "ffprobe tardó demasiado") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="replace").strip()
        raise StickerError("No pude leer el video.", f"ffprobe falló: {detail}")

    meta = json.loads(proc.stdout or b"{}")
    streams = meta.get("streams") or []
    if not streams:
        raise StickerError("El archivo no tiene video.", "ffprobe no encontró streams de video")
    stream = streams[0]

    duration = None
    for raw in (meta.get("format", {}).get("duration"), stream.get("duration")):
        try:
            duration = float(raw)
            break
        except (TypeError, ValueError):
            continue
    if duration is None:
        raise StickerError("No pude leer la duración del video.", f"ffprobe sin duración: {meta}")

    width, height = int(stream.get("width") or 0), int(stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise StickerError("No pude leer el video.", f"dimensiones inválidas: {stream}")

    rotation = stream.get("tags", {}).get("rotate")
    for side in stream.get("side_data_list") or []:
        rotation = side.get("rotation", rotation)
    try:
        if abs(int(float(rotation or 0))) % 180 == 90:
            width, height = height, width
    except ValueError:
        pass
    return VideoInfo(duration=duration, width=width, height=height)


def _ffmpeg_webp(
    src: Path,
    dst: Path,
    *,
    fps: int,
    quality: int,
    side: int,
    seconds: float,
    watermark: Path | None,
    margin: int,
    timeout: float,
) -> None:
    pad = f"pad={CANVAS}:{CANVAS}:(ow-iw)/2:(oh-ih)/2:color=black@0,format=yuva420p"
    base = (
        f"[0:v]fps={fps},"
        f"scale={side}:{side}:force_original_aspect_ratio=decrease:flags=lanczos,format=rgba"
    )
    if watermark is not None:
        graph = f"{base}[v];[v][1:v]overlay=x=W-w-{margin}:y=H-h-{margin}:format=auto,format=rgba,{pad}[out]"
    else:
        graph = f"{base},{pad}[out]"

    cmd = [_require("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
           "-t", f"{seconds:.3f}", "-i", str(src)]  # fmt: skip
    if watermark is not None:
        cmd += ["-i", str(watermark)]
    cmd += [
        "-filter_complex", graph,
        "-map", "[out]",
        "-an",
        "-c:v", "libwebp_anim",
        "-lossless", "0",
        "-quality", str(quality),
        "-compression_level", "4",
        "-loop", "0",
        str(dst),
    ]  # fmt: skip
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise StickerError("El video tardó demasiado en procesarse.", f"ffmpeg superó {timeout}s") from exc
    if proc.returncode != 0 or not dst.exists():
        detail = proc.stderr.decode(errors="replace").strip()
        raise StickerError("No pude convertir el video.", f"ffmpeg falló: {detail}")


def _finish_animated(webp: bytes, exif: bytes, opts: StickerOptions) -> bytes:
    try:
        webp = add_exif_to_webp(webp, exif)
    except ValueError:
        pass  # WebP simple (sin VP8X): se reescribe abajo como estático
    with Image.open(io.BytesIO(webp)) as img:
        if getattr(img, "n_frames", 1) > 1:
            return webp
        # Un "video" de un solo cuadro se manda como sticker estático de verdad.
        return _encode_static(img.convert("RGBA"), exif, opts.image_max_bytes)


def video_to_sticker(data: bytes, opts: StickerOptions = DEFAULT_OPTIONS) -> bytes:
    """Convierte un video corto o GIF en un sticker WebP animado."""
    exif = build_exif(opts.pack_name, opts.publisher)
    budget = opts.animated_max_bytes - (len(exif) + 8 + 1)  # el chunk EXIF también cuenta

    with tempfile.TemporaryDirectory(prefix="licha-sticker-") as tmp:
        tmpdir = Path(tmp)
        src = tmpdir / "input"
        src.write_bytes(data)

        info = probe_video(src)
        if info.duration > opts.max_video_seconds + DURATION_TOLERANCE:
            raise StickerError(
                f"El video dura {info.duration:.0f} s; el máximo es {opts.max_video_seconds:g} s.",
                f"video de {info.duration:.2f}s rechazado",
            )
        seconds = min(info.duration, opts.max_video_seconds) or opts.max_video_seconds

        wm_path: Path | None = None
        margin = 0
        if opts.watermark:
            cw, ch = fit_size(info.width, info.height)
            mark, margin = _watermark_for(opts.watermark, cw, ch)
            wm_path = tmpdir / "watermark.png"
            mark.save(wm_path)

        best: bytes | None = None
        attempt = 0
        while attempt < len(ANIMATED_LADDER):
            fps, quality, side = ANIMATED_LADDER[attempt]
            dst = tmpdir / f"out{attempt}.webp"
            _ffmpeg_webp(
                src, dst,
                fps=fps, quality=quality, side=side, seconds=seconds,
                watermark=wm_path, margin=margin, timeout=opts.ffmpeg_timeout,
            )  # fmt: skip
            out = dst.read_bytes()
            log.debug("Intento %d (fps=%d q=%d lado=%d): %d bytes", attempt, fps, quality, side, len(out))
            if best is None or len(out) < len(best):
                best = out
            if len(out) <= budget:
                break
            # Cuanto más lejos del objetivo, más escalones saltamos (cada intento tarda segundos).
            ratio = len(out) / budget
            attempt += 1 if ratio <= 1.5 else 2 if ratio <= 3 else 3

        assert best is not None
        if len(best) > budget:
            log.warning("Sticker animado de %d bytes supera el objetivo de %d", len(best), opts.animated_max_bytes)
        return _finish_animated(best, exif, opts)


# --------------------------------------------------------------------------- #
# Utilidades para pruebas y uso por consola
# --------------------------------------------------------------------------- #


def inspect_webp(data: bytes) -> dict:
    """Datos básicos de un sticker WebP (tamaño, cuadros, metadatos)."""
    exif_json = None
    for fourcc, payload in iter_webp_chunks(data):
        if fourcc == b"EXIF" and len(payload) > 22:
            exif_json = json.loads(payload[22:].decode("utf-8"))
    with Image.open(io.BytesIO(data)) as img:
        return {
            "bytes": len(data),
            "width": img.width,
            "height": img.height,
            "frames": getattr(img, "n_frames", 1),
            "animated": getattr(img, "is_animated", False),
            "exif": exif_json,
        }


def convert_auto(data: bytes, opts: StickerOptions = DEFAULT_OPTIONS) -> bytes:
    """Imagen estática -> sticker estático; cualquier otra cosa -> animado."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            animated = getattr(img, "is_animated", False)
    except (UnidentifiedImageError, OSError):
        animated = True  # Pillow no lo abre: probablemente sea un video
    if not animated:
        return image_to_sticker(data, opts)
    try:
        return video_to_sticker(data, opts)
    except StickerError as exc:
        if exc.user_message.startswith("No pude leer el video"):
            raise StickerError("No pude leer el archivo (¿es una imagen o un video?).", str(exc)) from exc
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convierte una imagen o video en sticker de WhatsApp.")
    parser.add_argument("entrada", type=Path)
    parser.add_argument("salida", type=Path)
    parser.add_argument("--marca", default=StickerOptions.watermark, help='texto visible ("" para quitarlo)')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")

    opts = StickerOptions(watermark=args.marca)
    try:
        out = convert_auto(args.entrada.read_bytes(), opts)
    except StickerError as exc:
        print(f"Error: {exc.user_message} ({exc})", file=sys.stderr)
        return 1
    args.salida.write_bytes(out)
    print(json.dumps(inspect_webp(out), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
