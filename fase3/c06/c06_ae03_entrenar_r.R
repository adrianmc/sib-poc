# C06-AE-03: mismo caso de uso en R, en el MISMO proyecto CML (sesion con runtime R 4.x).
# Lee las features preparadas por el paso Python (mismo flujo) y entrena una regresion logistica.
datos <- read.csv("/home/cdsw/data/features_creditos.csv")
datos$segmento <- as.factor(datos$segmento)
datos$region <- as.factor(datos$region)

# Exploracion (C06-PRE-03)
print(summary(datos[, c("monto_original", "saldo_pendiente", "dias_mora", "ingreso_mensual", "carga_financiera")]))
print(aggregate(default_12m ~ segmento, data = datos, FUN = mean))

set.seed(42)
idx <- sample(seq_len(nrow(datos)), size = 0.75 * nrow(datos))
entreno <- datos[idx, ]
prueba <- datos[-idx, ]

modelo <- glm(default_12m ~ dias_mora + carga_financiera + tasa_interes + plazo_meses + segmento + region,
              data = entreno, family = binomial())
print(summary(modelo))

auc <- function(y, p) {           # AUC sin paquetes externos (estadistico de Mann-Whitney)
  r <- rank(p); n1 <- sum(y == 1); n0 <- sum(y == 0)
  (sum(r[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0)
}
p <- predict(modelo, newdata = prueba, type = "response")
cat(sprintf("\nAUC (R, regresion logistica): %.4f\n", auc(prueba$default_12m, p)))
write.csv(data.frame(modelo = "glm-R", auc = auc(prueba$default_12m, p), filas_entreno = nrow(entreno)),
          "/home/cdsw/data/resultado_r.csv", row.names = FALSE)
saveRDS(modelo, "/home/cdsw/data/modelo_glm_r.rds")
# Registro: ejecutar luego fase3/c06/c06_ae03_registrar_r.py (registra metricas y artefacto R en MLflow)
