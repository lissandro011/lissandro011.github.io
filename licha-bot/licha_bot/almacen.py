"""Datos que sobreviven a un reinicio (datos/licha.sqlite3).

- Decretos (!decreto): una votación abierta por grupo y un voto por persona.
- Planes (!confirmo): una lista abierta por grupo y un estado por persona.
- Grupos autorizados por el dueño (ver guardia.py).
- Chats que ya vieron el !menu (para el saludo de la primera vez).

Las claves primarias y los índices únicos hacen que un voto o una respuesta
repetidos nunca sumen dos veces, aunque lleguen dos mensajes juntos.
No se guarda el texto de las preguntas a la bola 8 ni nada parecido.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS meta (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS decretos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat TEXT NOT NULL,
    texto TEXT NOT NULL,
    autor TEXT NOT NULL,
    abierto INTEGER NOT NULL DEFAULT 1,
    creado REAL NOT NULL,
    cerrado REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS decreto_abierto_por_chat ON decretos(chat) WHERE abierto = 1;

CREATE TABLE IF NOT EXISTS votos (
    decreto INTEGER NOT NULL REFERENCES decretos(id),
    persona TEXT NOT NULL,
    voto TEXT NOT NULL CHECK (voto IN ('sí', 'no')),
    PRIMARY KEY (decreto, persona)
);

CREATE TABLE IF NOT EXISTS planes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat TEXT NOT NULL,
    nombre TEXT NOT NULL,
    organizador TEXT NOT NULL,
    abierto INTEGER NOT NULL DEFAULT 1,
    creado REAL NOT NULL,
    cerrado REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS plan_abierto_por_chat ON planes(chat) WHERE abierto = 1;

CREATE TABLE IF NOT EXISTS respuestas (
    plan INTEGER NOT NULL REFERENCES planes(id),
    persona TEXT NOT NULL,
    nombre TEXT NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('voy', 'capaz', 'me bajo')),
    orden REAL NOT NULL,
    PRIMARY KEY (plan, persona)
);

CREATE TABLE IF NOT EXISTS mensajes_plan (
    chat TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    plan INTEGER NOT NULL REFERENCES planes(id),
    PRIMARY KEY (chat, mensaje)
);

CREATE TABLE IF NOT EXISTS grupos (
    chat TEXT PRIMARY KEY,
    estado TEXT NOT NULL CHECK (estado IN ('autorizado', 'pendiente')),
    nombre TEXT NOT NULL DEFAULT '',
    agregado_por TEXT NOT NULL DEFAULT '',
    codigo TEXT,
    vence REAL,
    avisado INTEGER NOT NULL DEFAULT 0  -- 1 si al dueño le llegó el aviso por privado
);

CREATE TABLE IF NOT EXISTS menu_visto (chat TEXT PRIMARY KEY);
"""

ESTADOS_PLAN = ("voy", "capaz", "me bajo")


@dataclass(frozen=True)
class Decreto:
    id: int
    chat: str
    texto: str
    autor: str
    abierto: bool


@dataclass(frozen=True)
class Plan:
    id: int
    chat: str
    nombre: str
    organizador: str
    abierto: bool


@dataclass(frozen=True)
class GrupoPendiente:
    chat: str
    nombre: str
    agregado_por: str
    codigo: str
    vence: float  # time.time()
    avisado: bool = False  # True si al dueño le llegó el aviso por privado


class Almacen:
    def __init__(self, archivo: Path | str):
        if isinstance(archivo, Path):
            archivo.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(archivo), isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(ESQUEMA)  # crea las tablas que falten (executescript maneja su propia transacción)
            self._migrar()
        if archivo != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")

    def _migrar(self) -> None:
        """Agrega las columnas nuevas a bases de datos de versiones anteriores."""
        columnas = {fila["name"] for fila in self._db.execute("PRAGMA table_info(grupos)")}
        if columnas and "avisado" not in columnas:
            # Los grupos que ya estaban esperando quedan como "no avisados": así el bot
            # le vuelve a avisar al dueño en cuanto pueda (ver guardia.py).
            self._db.execute("ALTER TABLE grupos ADD COLUMN avisado INTEGER NOT NULL DEFAULT 0")

    def cerrar(self) -> None:
        self._db.close()

    @contextmanager
    def _transaccion(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self._db
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            self._db.execute("COMMIT")

    # -- meta y menú ---------------------------------------------------------- #

    def meta(self, clave: str) -> str | None:
        with self._transaccion() as db:
            fila = db.execute("SELECT valor FROM meta WHERE clave = ?", (clave,)).fetchone()
        return fila["valor"] if fila else None

    def poner_meta(self, clave: str, valor: str) -> None:
        with self._transaccion() as db:
            db.execute("INSERT INTO meta VALUES (?, ?) ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
                       (clave, valor))  # fmt: skip

    def primera_vez_menu(self, chat: str) -> bool:
        """True la primera vez que se pide el menú en ese chat (y lo anota)."""
        with self._transaccion() as db:
            return db.execute("INSERT OR IGNORE INTO menu_visto VALUES (?)", (chat,)).rowcount == 1

    # -- decretos -------------------------------------------------------------- #

    @staticmethod
    def _decreto(fila: sqlite3.Row | None) -> Decreto | None:
        if fila is None:
            return None
        return Decreto(fila["id"], fila["chat"], fila["texto"], fila["autor"], bool(fila["abierto"]))

    def decreto_abierto(self, chat: str) -> Decreto | None:
        with self._transaccion() as db:
            return self._decreto(
                db.execute("SELECT * FROM decretos WHERE chat = ? AND abierto = 1", (chat,)).fetchone()
            )

    def abrir_decreto(self, chat: str, texto: str, autor: str) -> tuple[Decreto, bool]:
        """Abre una votación. Si ya había una abierta, devuelve esa y False."""
        with self._transaccion() as db:
            abierto = db.execute("SELECT * FROM decretos WHERE chat = ? AND abierto = 1", (chat,)).fetchone()
            if abierto is not None:
                return self._decreto(abierto), False  # type: ignore[return-value]
            cursor = db.execute(
                "INSERT INTO decretos (chat, texto, autor, creado) VALUES (?, ?, ?, ?)",
                (chat, texto, autor, time.time()),
            )
            return Decreto(cursor.lastrowid or 0, chat, texto, autor, True), True

    def votar(self, decreto: int, persona: str, voto: str) -> str | None:
        """Guarda el voto ('sí' o 'no') y devuelve el voto anterior de esa persona (o None)."""
        with self._transaccion() as db:
            fila = db.execute("SELECT voto FROM votos WHERE decreto = ? AND persona = ?", (decreto, persona)).fetchone()
            db.execute(
                "INSERT INTO votos VALUES (?, ?, ?) ON CONFLICT(decreto, persona) DO UPDATE SET voto = excluded.voto",
                (decreto, persona, voto),
            )
        return fila["voto"] if fila else None

    def contar_votos(self, decreto: int) -> tuple[int, int]:
        """(votos por sí, votos por no)."""
        with self._transaccion() as db:
            filas = dict(db.execute("SELECT voto, COUNT(*) FROM votos WHERE decreto = ? GROUP BY voto", (decreto,)))
        return filas.get("sí", 0), filas.get("no", 0)

    def cerrar_decreto(self, decreto: int) -> bool:
        """Cierra la votación. False si ya estaba cerrada (por ejemplo, dos !decreto cerrar juntos)."""
        with self._transaccion() as db:
            cursor = db.execute("UPDATE decretos SET abierto = 0, cerrado = ? WHERE id = ? AND abierto = 1",
                                (time.time(), decreto))  # fmt: skip
            return cursor.rowcount == 1

    # -- planes ---------------------------------------------------------------- #

    @staticmethod
    def _plan(fila: sqlite3.Row | None) -> Plan | None:
        if fila is None:
            return None
        return Plan(fila["id"], fila["chat"], fila["nombre"], fila["organizador"], bool(fila["abierto"]))

    def plan_abierto(self, chat: str) -> Plan | None:
        with self._transaccion() as db:
            return self._plan(db.execute("SELECT * FROM planes WHERE chat = ? AND abierto = 1", (chat,)).fetchone())

    def abrir_plan(self, chat: str, nombre: str, organizador: str) -> tuple[Plan, bool]:
        """Abre una lista. Si ya había una abierta, devuelve esa y False."""
        with self._transaccion() as db:
            abierto = db.execute("SELECT * FROM planes WHERE chat = ? AND abierto = 1", (chat,)).fetchone()
            if abierto is not None:
                return self._plan(abierto), False  # type: ignore[return-value]
            cursor = db.execute(
                "INSERT INTO planes (chat, nombre, organizador, creado) VALUES (?, ?, ?, ?)",
                (chat, nombre, organizador, time.time()),
            )
            return Plan(cursor.lastrowid or 0, chat, nombre, organizador, True), True

    def responder_plan(self, plan: int, persona: str, nombre: str, estado: str) -> str | None:
        """Guarda el estado de esa persona y devuelve el que tenía antes (o None)."""
        if estado not in ESTADOS_PLAN:
            raise ValueError(estado)
        with self._transaccion() as db:
            fila = db.execute(
                "SELECT estado FROM respuestas WHERE plan = ? AND persona = ?", (plan, persona)
            ).fetchone()
            anterior = fila["estado"] if fila else None
            if anterior == estado:
                db.execute("UPDATE respuestas SET nombre = ? WHERE plan = ? AND persona = ?", (nombre, plan, persona))
            else:  # al cambiar de estado pasa al final de su nueva lista
                db.execute(
                    "INSERT INTO respuestas VALUES (?, ?, ?, ?, ?) ON CONFLICT(plan, persona) DO UPDATE SET "
                    "nombre = excluded.nombre, estado = excluded.estado, orden = excluded.orden",
                    (plan, persona, nombre, estado, time.time()),
                )
        return anterior

    def respuestas_plan(self, plan: int) -> dict[str, list[str]]:
        """{'voy': [nombres], 'capaz': [...], 'me bajo': [...]} en orden de llegada."""
        resultado: dict[str, list[str]] = {estado: [] for estado in ESTADOS_PLAN}
        with self._transaccion() as db:
            for fila in db.execute(
                "SELECT nombre, estado FROM respuestas WHERE plan = ? ORDER BY orden, rowid", (plan,)
            ):
                resultado[fila["estado"]].append(fila["nombre"])
        return resultado

    def cerrar_plan(self, plan: int) -> bool:
        with self._transaccion() as db:
            cursor = db.execute("UPDATE planes SET abierto = 0, cerrado = ? WHERE id = ? AND abierto = 1",
                                (time.time(), plan))  # fmt: skip
            return cursor.rowcount == 1

    def anotar_mensaje_plan(self, chat: str, mensaje: str, plan: int) -> None:
        """Recuerda que ese mensaje del bot es la convocatoria o un resumen del plan."""
        if not mensaje:
            return
        with self._transaccion() as db:
            db.execute("INSERT OR REPLACE INTO mensajes_plan VALUES (?, ?, ?)", (chat, mensaje, plan))

    def plan_de_mensaje(self, chat: str, mensaje: str) -> Plan | None:
        """El plan al que pertenece ese mensaje del bot (abierto o cerrado), o None."""
        with self._transaccion() as db:
            fila = db.execute(
                "SELECT planes.* FROM mensajes_plan JOIN planes ON planes.id = mensajes_plan.plan "
                "WHERE mensajes_plan.chat = ? AND mensajes_plan.mensaje = ?",
                (chat, mensaje),
            ).fetchone()
        return self._plan(fila)

    # -- grupos autorizados ------------------------------------------------------ #

    def estado_grupo(self, chat: str) -> str | None:
        """'autorizado', 'pendiente' o None si el bot no lo conoce."""
        with self._transaccion() as db:
            fila = db.execute("SELECT estado FROM grupos WHERE chat = ?", (chat,)).fetchone()
        return fila["estado"] if fila else None

    def autorizar_grupo(self, chat: str, nombre: str = "") -> None:
        with self._transaccion() as db:
            db.execute(
                "INSERT INTO grupos (chat, estado, nombre) VALUES (?, 'autorizado', ?) ON CONFLICT(chat) DO UPDATE SET "
                "estado = 'autorizado', codigo = NULL, vence = NULL, "
                "nombre = CASE WHEN excluded.nombre <> '' THEN excluded.nombre ELSE grupos.nombre END",
                (chat, nombre),
            )

    def grupo_pendiente(self, chat: str, nombre: str, agregado_por: str, codigo: str, vence: float) -> bool:
        """Anota que el grupo espera permiso. False si ya estaba autorizado o pendiente."""
        with self._transaccion() as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO grupos (chat, estado, nombre, agregado_por, codigo, vence, avisado) "
                "VALUES (?, 'pendiente', ?, ?, ?, ?, 0)",
                (chat, nombre, agregado_por, codigo, vence),
            )
            return cursor.rowcount == 1

    def pendientes(self) -> list[GrupoPendiente]:
        with self._transaccion() as db:
            filas = db.execute("SELECT * FROM grupos WHERE estado = 'pendiente' ORDER BY vence").fetchall()
        return [
            GrupoPendiente(f["chat"], f["nombre"], f["agregado_por"], f["codigo"], f["vence"], bool(f["avisado"]))
            for f in filas
        ]

    def marcar_avisado(self, chat: str) -> bool:
        """Anota que al dueño le llegó el aviso de ese grupo (para no repetírselo)."""
        with self._transaccion() as db:
            return db.execute("UPDATE grupos SET avisado = 1 WHERE chat = ?", (chat,)).rowcount == 1

    def autorizados(self) -> list[tuple[str, str]]:
        """[(chat, nombre)] de los grupos autorizados."""
        with self._transaccion() as db:
            return [
                (f["chat"], f["nombre"])
                for f in db.execute("SELECT chat, nombre FROM grupos WHERE estado = 'autorizado'")
            ]

    def borrar_grupo(self, chat: str) -> bool:
        with self._transaccion() as db:
            return db.execute("DELETE FROM grupos WHERE chat = ?", (chat,)).rowcount == 1
