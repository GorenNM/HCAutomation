# Datos reales

Excel de verdad, no inventados. La cultura del proyecto es verificar contra
datos reales (§13.2 del plan), así que viajan en el repo.

| Archivo | Qué es |
|---|---|
| `Reporte 5 Enero 2025.xlsx` | El reporte de entrada exportado de SIPI: los 987 expedientes de la corrida definitiva |
| `Excel_Report.xlsx` | El mismo tipo de export, pero **crudo**: trae las coordenadas de celda mal escritas que `excel/reader.py` repara en memoria al leerlo |
| `Negacion marcas con información extra.xlsx` | El resultado hecho a mano, la referencia contra la que se mide la salida del programa |
| `Negacion_marcas_20260807_213955.xlsx` | Una salida generada, la que compara `scripts/comparar_salida.py` por defecto |
| `Negacion_marcas_20260808_112758.xlsx` | Otra salida generada, de una corrida posterior |
| `discrepancias.csv` | Diferencias medidas entre la salida y la referencia |

Los recortes pequeños para pruebas offline no están aquí: viven en
`tests/data/`.
