# Databricks notebook source
# MAGIC # Gold Model  - bcb-lakehouse-databricks
# MAGIC
# MAGIC Constrói o modelo analítico da camada Gold a partir da Silver:
# MAGIC - `dim_data`: calendário completo cobrindo o range dos dados Silver
# MAGIC - `fct_indicadores`: uma linha por dia com as 3 séries como colunas
# MAGIC
# MAGIC **Decisões de modelagem:**
# MAGIC - USD/BRL e Selic: join direto por data (séries diárias)
# MAGIC - IPCA: join por `(ano, mes)`  - forward fill implícito para todos os dias do mês
# MAGIC - Tabelas gravadas com `overwrite` (Gold é modelo derivado, reconstruído integralmente)
# MAGIC - OPTIMIZE + ZORDER BY data aplicados após a escrita
# MAGIC
# MAGIC **ADRs que governam este notebook:**
# MAGIC - ADR-0006: Armazenamento em `/Volumes/bcb_lakehouse_databricks/default/gold/`
# MAGIC - ADR-0007: Registro no Unity Catalog (`bcb_lakehouse_databricks.default`)

# COMMAND ----------

#1. Configuração

CATALOG = "bcb_lakehouse_databricks"
SCHEMA = "default"
TABLE_SILVER = f"{CATALOG}.{SCHEMA}.silver_bcb"
TABLE_FCT = f"{CATALOG}.{SCHEMA}.fct_indicadores"
TABLE_DIM = f"{CATALOG}.{SCHEMA}.dim_data"

print(f"Fonte  : {TABLE_SILVER}")
print(f"Gold fato : {TABLE_FCT}")
print(f"Gold dim  : {TABLE_DIM}")

# COMMAND ----------

#2. Range de datas da Silver

row = spark.sql(f"SELECT MIN(data) AS min_d, MAX(data) AS max_d FROM {TABLE_SILVER}").collect()[0]
min_date = str(row["min_d"])
max_date = str(row["max_d"])

print(f"Range Silver: {min_date} → {max_date}")

# COMMAND ----------

#3. dim_data  - calendário completo

from pyspark.sql.functions import col, year, month, quarter, dayofweek, date_format, when

df_dim = spark.sql(f"""
SELECT explode(sequence(
    date('{min_date}'),
    date('{max_date}'),
    interval 1 day
)) AS data
""")

df_dim = (
    df_dim
    .withColumn("data_id",    date_format(col("data"), "yyyyMMdd").cast("integer"))
    .withColumn("ano",        year(col("data")))
    .withColumn("mes",        month(col("data")))
    .withColumn("trimestre",  quarter(col("data")))
    .withColumn("dia_semana", dayofweek(col("data")))
    .withColumn("is_dia_util",
        when(dayofweek(col("data")).isin(2, 3, 4, 5, 6), True).otherwise(False)
    )
)

print(f"dim_data: {df_dim.count()} dias ({min_date} → {max_date})")

# COMMAND ----------

#4. fct_indicadores  - pivot das 3 séries

df_usd = spark.sql(f"""
    SELECT data, valor AS usd_brl
    FROM {TABLE_SILVER} WHERE serie_id = '1'
""")

df_selic = spark.sql(f"""
    SELECT data, valor AS selic_aa
    FROM {TABLE_SILVER} WHERE serie_id = '11'
""")

df_ipca = spark.sql(f"""
    SELECT ano, mes, valor AS ipca_mensal
    FROM {TABLE_SILVER} WHERE serie_id = '433'
""")

df_fct = (
    df_dim
    .join(df_usd,   "data", "left")
    .join(df_selic, "data", "left")
    .join(df_ipca,  ["ano", "mes"], "left")
    .select("data", "ano", "mes", "usd_brl", "selic_aa", "ipca_mensal")
    .orderBy("data")
)

print(f"fct_indicadores: {df_fct.count()} linhas")

# COMMAND ----------

#5. Gravar dim_data

df_dim.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(TABLE_DIM)

print(f"[OK] {TABLE_DIM} gravada")

# COMMAND ----------

#6. Gravar fct_indicadores

df_fct.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(TABLE_FCT)

print(f"[OK] {TABLE_FCT} gravada")

# COMMAND ----------

#7. OPTIMIZE + ZORDER

spark.sql(f"OPTIMIZE {TABLE_FCT} ZORDER BY (data)")
print("[OK] OPTIMIZE + ZORDER BY data aplicados")

# COMMAND ----------

#8. Time travel (demonstração)

print("Versão 0 da fct_indicadores (time travel):")
display(spark.sql(f"""
SELECT * FROM {TABLE_FCT} VERSION AS OF 0
LIMIT 5
"""))

# COMMAND ----------

#9. Validação

display(spark.sql(f"""
SELECT
    COUNT(*)            AS total_dias,
    COUNT(usd_brl)      AS dias_com_cambio,
    COUNT(selic_aa)     AS dias_com_selic,
    COUNT(ipca_mensal)  AS dias_com_ipca,
    MIN(data)           AS primeiro_dia,
    MAX(data)           AS ultimo_dia
FROM {TABLE_FCT}
"""))
