"""
Genera documentos FICTICIOS de prueba en fixtures/generados/.
Responsable: PERSONA_3. Nunca usar datos reales.

Casos previstos:
  - sano:              los 3 documentos coinciden y estan vigentes
  - domicilio_distinto: credencial y comprobante con domicilio diferente
  - vencido:           pasaporte con fecha_vencimiento en el pasado
  - duplicado:         mismo archivo subido dos veces (mismo hash)
Modalidades por documento: PDF digital (reportlab/fitz), PDF escaneado (render a imagen + PDF), imagen JPG.
"""
from pathlib import Path

PERSONAS_FICTICIAS = [
    {"nombre_completo": "Ana Ejemplo Prueba", "fecha_nacimiento": "1990-01-01",
     "curp": "AEPA900101MDFXXX01", "domicilio": "Calle Ficticia 123, Colonia Demo, Ciudad Ejemplo"},
    {"nombre_completo": "Luis Demo Pruebas", "fecha_nacimiento": "1985-06-15",
     "curp": "DEPL850615HDFXXX02", "domicilio": "Avenida Inventada 456, Colonia Test, Ciudad Ejemplo"},
]

SALIDA = Path(__file__).resolve().parent.parent / "fixtures" / "generados"


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    # TODO PERSONA_3: generar con Pillow/PyMuPDF los documentos por caso y modalidad.
    print(f"Fixtures se generaran en {SALIDA}")


if __name__ == "__main__":
    main()
