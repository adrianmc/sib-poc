# C02-AE-03: incremento significativo de carga, batch y streaming (antes / despues)

Criterio: la plataforma ajusta recursos sin intervencion manual y mantiene desempeno dentro del umbral.
Umbrales propuestos (confirmar con la SIB): batch <= 2x el tiempo base con 3x el volumen; streaming p95 <= 60 s; SQL p95 <= 5 s.

## SQL interactivo (Impala, WAA)
`c02_prueba_carga.py --prueba autoscaling --niveles 50,500 --segundos 180`. Evidencia: Grafana del VW (ejecutores
activos subiendo y bajando) + `sb_consumption.metricas_rendimiento`. Nativo.

## Batch (CDE, autoscaling de ejecutores y nodos)
1. Base: `sb-pipeline-batch` con `parquet_masivo` de 10M (job 02 con `--millones 10`). Anotar duracion y ejecutores (CDE > Job Runs > Spark UI > Executors).
2. Carga: regenerar `parquet_masivo` con `--millones 30` y re-ejecutar sin cambiar la configuracion del job.
3. Evidencia: duracion de ambas corridas en `sb_consumption.pipeline_runs`; numero maximo de ejecutores (dynamic allocation)
   y nodos del VC (CDE > Virtual Cluster > Grafana). Registros/ms = filas / duracion. Nativo.

## Streaming (Kafka + Spark Structured Streaming en CDE)
1. Base: productor a 20 eventos/s y medicion `--medir --tasa-fondo 20`.
2. Carga: segundo productor a 500 eventos/s (`--eventos 150000 --por-segundo 500`, varias instancias si hace falta) y `--medir --tasa-fondo 500`.
3. Evidencia: `sb_consumption.latencia_streaming` (antes/despues) y ejecutores del job streaming.
Declarar con precision: Spark (consumidor) escala ejecutores solo; **los brokers de Kafka del Data Hub no autoescalan**
(se dimensionan o escalan manualmente). Resultado esperado: workaround/parcial para streaming.
