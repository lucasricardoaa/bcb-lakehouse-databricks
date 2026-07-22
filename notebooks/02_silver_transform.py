# Databricks notebook source
# MAGIC # Silver Transform  - bcb-lakehouse-databricks
# MAGIC
# MAGIC Transforma os dados brutos da camada Bronze: limpeza, tipagem e deduplicação.
# MAGIC Grava na camada Silver com MERGE INTO incremental e idempotente.
# MAGIC
# MAGIC **Transformações aplicadas:**
# MAGIC - `data`: STRING (dd/MM/yyyy) → DateType
# MAGIC - `valor`: STRING → DoubleType
# MAGIC - Remoção de registros com `valor IS NULL`
# MAGIC - Adição de colunas derivadas `ano` e `mes`
# MAGIC
# MAGIC **ADRs que governam este notebook:**
# MAGIC - ADR-0002: MERGE INTO com chave `(serie_id, data)` para idempotência
# MAGIC - ADR-0006: Armazenamento em `/Volumes/bcb_lakehouse_databricks/default/silver/bcb/`
# MAGIC - ADR-0007: Registro no Unity Catalog (`bcb_lakehouse_databricks.default.silver_bcb`)

# COMMAND ----------

#Parâmetros

dbutils.widgets.text("data_inicio", "", "Data início (dd/MM/yyyy)")
dbutils.widgets.text("data_fim", "", "Data fim (dd/MM/yyyy)")

# COMMAND ----------

from datetime import datetime, timedelta

data_inicio = dbutils.widgets.get("data_inicio")
data_fim = dbutils.widgets.get("data_fim")

if not data_inicio:
    data_inicio = (datetime.now() - timedelta(days=30)).strftime("%d/%m/%Y")
if not data_fim:
    data_fim = datetime.now().strftime("%d/%m/%Y")

print(f"Janela de processamento: {data_inicio} → {data_fim}")

# COMMAND ----------

#1. Configuração

CATALOG = "bcb_lakehouse_databricks"
SCHEMA = "default"
TABLE_BRONZE = f"{CATALOG}.{SCHEMA}.bronze_bcb"
TABLE_SILVER = f"{CATALOG}.{SCHEMA}.silver_bcb"

print(f"Fonte  : {TABLE_BRONZE}")
print(f"Destino: {TABLE_SILVER}")

# COMMAND ----------

#2. Leitura e filtragem da Bronze

from pyspark.sql.functions import to_date, col, lit, year, month
from datetime import datetime

dt_inicio = datetime.strptime(data_inicio, "%d/%m/%Y").strftime("%Y-%m-%d")
dt_fim = datetime.strptime(data_fim, "%d/%m/%Y").strftime("%Y-%m-%d")

df_bronze = spark.table(TABLE_BRONZE)

df_filtered = df_bronze.filter(
    to_date(col("data"), "dd/MM/yyyy").between(lit(dt_inicio), lit(dt_fim))
)

print(f"Registros na janela: {df_filtered.count()}")

# COMMAND ----------

#3. Transformações

df_silver = (
    df_filtered
    .withColumn("data",  to_date(col("data"), "dd/MM/yyyy"))
    .withColumn("valor", col("valor").cast("double"))
    .filter(col("valor").isNotNull())
    .withColumn("ano", year(col("data")))
    .withColumn("mes", month(col("data")))
    .select("data", "valor", "serie_id", "nome_serie", "ano", "mes", "ingest_ts")
)

print(f"Registros após limpeza: {df_silver.count()}")
df_silver.printSchema()

# COMMAND ----------

#4. Criar tabela Silver no Unity Catalog (ADR-0007)

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {TABLE_SILVER} (
    data       DATE      COMMENT 'Data do registro',
    valor      DOUBLE    COMMENT 'Valor da série (tipado)',
    serie_id   STRING    COMMENT 'Código da série BCB',
    nome_serie STRING    COMMENT 'Nome legível da série',
    ano        INT       COMMENT 'Ano extraído de data',
    mes        INT       COMMENT 'Mês extraído de data',
    ingest_ts  STRING    COMMENT 'Timestamp de ingestão original da Bronze'
)
USING DELTA
""")

print(f"[OK] Tabela {TABLE_SILVER} pronta")

# COMMAND ----------

#5. MERGE INTO  - upsert incremental (ADR-0002)

df_silver.createOrReplaceTempView("silver_novos")

spark.sql(f"""
MERGE INTO {TABLE_SILVER} AS destino
USING silver_novos AS origem
ON destino.serie_id = origem.serie_id
AND destino.data = origem.data
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
""")

print("[OK] MERGE INTO silver concluído")

# COMMAND ----------

#6. Validação

display(spark.sql(f"""
SELECT
    serie_id,
    nome_serie,
    typeof(valor)  AS tipo_valor,
    typeof(data)   AS tipo_data,
    COUNT(*)       AS total,
    COUNT(DISTINCT data) AS datas_unicas
FROM {TABLE_SILVER}
GROUP BY serie_id, nome_serie, typeof(valor), typeof(data)
ORDER BY serie_id
"""))
