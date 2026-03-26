"""
Entidad central del dominio, registro de una venta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import ClassVar
from datetime import date, datetime 

MESES: dict[str, int] = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


@dataclass(frozen=True)
class VentaRecord:
    """
    Registro de venta limpio y transformado, listo para persistencia.

    Transformaciones aplicadas:
      1. Separación de 'mes' → (mes_nombre, mes_num, anno y mes_og)
      2. Codificación label-encoding de región → region_code
    """

    # ── Campos originales normalizados ──────────────────────────────────────
    producto: str
    region: str

    # ── Transformación 1: separación de campo 'mes' ──────────────────────
    mes_nombre: str    # "Enero"
    mes_num: int       # 1
    anno: int          # 2022
    mes_og: str
    fecha: date

    # ── Transformación 2: codificación ordinal de región ─────────────────
    region_code: int   # 0-based encoding de la región

    # ── Métricas ─────────────────────────────────────────────────────────
    ventas_mensuales: int

    # ── Auditoría ────────────────────────────────────────────────────────
    procesado_en: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    # Tabla de codificación conocida (expandible)
    _REGION_ENCODING: ClassVar[dict[str, int]] = {
        "región 1": 0,
        "región 2": 1,
        "región 3": 2,
        "región 4": 3,
        "región 5": 4,
    }

    # ── Factory method ───────────────────────────────────────────────────

    @classmethod
    def from_raw(cls, raw: dict) -> "VentaRecord":
        """
        Construye un VentaRecord a partir de un dict crudo.
        Aplica todas las transformaciones del dominio.

        Raises:
            ValueError: si algún campo requerido falta o es inválido.
        """
        producto = cls._limpiar_str(raw.get("producto", ""), "producto")
        region   = cls._limpiar_str(raw.get("region",   ""), "region")

        mes_raw = cls._limpiar_str(raw.get("mes", ""), "mes")
        mes_nombre, mes_num, anno = cls._parsear_mes(mes_raw)
        fecha = date(anno, mes_num, 1)

        ventas = cls._validar_ventas(raw.get("ventas_mensuales"))
        region_code = cls._codificar_region(region)

        return cls(
            producto=producto,
            region=region,
            mes_nombre=mes_nombre,
            mes_num=mes_num,
            anno=anno,
            fecha=fecha,
            region_code=region_code,
            ventas_mensuales=ventas,
            mes_og=mes_raw
        )

    # ── Helpers privados ─────────────────────────────────────────────────

    @staticmethod
    def _limpiar_str(valor: str | None, campo: str) -> str:
        if not valor or not str(valor).strip():
            raise ValueError(f"Campo '{campo}' vacío o ausente.")
        return str(valor).strip()

    @staticmethod
    def _parsear_mes(mes_raw: str) -> tuple[str, int, int]:
        """
        Transforma "Enero 2022" → ("Enero", 1, 2022).
        Acepta variantes con espacios extra y tildes.
        """
        partes = mes_raw.strip().split()
        if len(partes) != 2:
            raise ValueError(
                f"Formato de mes inválido: '{mes_raw}'. "
                "Se esperaba '<Mes> <YYYY>' (ej. 'Enero 2022')."
            )
        nombre_raw, anno_raw = partes

        nombre_key = nombre_raw.lower()
        # Normalizar tildes comunes para robustez
        nombre_key = nombre_key.replace("á", "a").replace("é", "e") \
                               .replace("í", "i").replace("ó", "o").replace("ú", "u")

        num = MESES.get(nombre_key)
        if num is None:
            raise ValueError(f"Nombre de mes desconocido: '{nombre_raw}'.")

        if not re.fullmatch(r"\d{4}", anno_raw):
            raise ValueError(f"Año inválido: '{anno_raw}'. Se esperaban 4 dígitos.")

        return nombre_raw.capitalize(), num, int(anno_raw)

    @staticmethod
    def _validar_ventas(valor) -> int:
        try:
            v = int(valor)
        except (TypeError, ValueError):
            raise ValueError(f"ventas_mensuales no es numérico: '{valor}'.")
        if v < 0:
            raise ValueError(f"ventas_mensuales no puede ser negativo: {v}.")
        return v

    @classmethod
    def _codificar_region(cls, region: str) -> int:
        """
        Label-encoding de la región.
        Si la región no está en el catálogo, se asigna código -1
        para identificarla como 'desconocida' sin lanzar excepción.
        """
        key = region.lower()
        return cls._REGION_ENCODING.get(key, -1)

    # ── Serialización ────────────────────────────────────────────────────

    def to_bq_row(self) -> dict:
        """Devuelve el registro como objeto compatible con BigQuery insert_rows_json."""
        return {
            "producto":          self.producto,
            "region":            self.region,
            "region_code":       self.region_code,
            "mes_nombre":        self.mes_nombre,
            "mes_num":           self.mes_num,
            "mes_og":            self.mes_og,
            "fecha":            self.fecha.isoformat(),
            "anno":              self.anno,
            "ventas_mensuales":  self.ventas_mensuales,
            "procesado_en":      self.procesado_en,
        }
