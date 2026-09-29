# orquestador  (responsable: PERSONA_2)

Entrada: `preparar(bytes, nombre, tipo_declarado)`.
Salida: `DocumentoPreparado` (Contrato 3): modalidad (`pdf_digital` | `pdf_escaneado` | `imagen`)
y `paginas` en orden, cada una con texto (PyMuPDF u OCR) y/o PNG para el modelo de vision.
OCR detras de `OCRProvider` (Tesseract en el MVP).
