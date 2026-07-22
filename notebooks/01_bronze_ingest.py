# Databricks notebook source
# MAGIC # Bronze Ingest — bcb-lakehouse-databricks
# MAGIC
# MAGIC Ingere séries históricas da API do Banco Central do Brasil (BCB) para a camada Bronze do Delta Lake.
# MAGIC
# MAGIC **Séries ingeridas:**
# MAGIC - `1` — Câmbio USD/BRL (frequência diária)
# MAGIC - `11` — Taxa Selic (frequência diária)
# MAGIC - `433` — IPCA (frequência mensal)
# MAGIC
# MAGIC **ADRs que governam este notebook:**
# MAGIC - ADR-0002: MERGE INTO como estratégia de ingestão incremental (chave: `serie_id + data`)
# MAGIC - ADR-0006: Armazenamento em Unity Catalog Volumes (`/Volumes/bcb_lakehouse_databricks/default/bronze/bcb/`)
# MAGIC - ADR-0007: Registro de tabelas no Unity Catalog (`bcb_lakehouse_databricks.default.bronze_bcb`)

# COMMAND ----------

# MAGIC ## Parâmetros

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

print(f"Janela de ingestão: {data_inicio} → {data_fim}")

# COMMAND ----------

# MAGIC ## 1. Configuração

CATALOG = "bcb_lakehouse_databricks"
SCHEMA = "default"
TABLE_BRONZE = f"{CATALOG}.{SCHEMA}.bronze_bcb"
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/bronze/bcb/"

SERIES = {
    "1":   "USD/BRL",
    "11":  "Selic",
    "433": "IPCA",
}

BCB_BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie_id}/dados"

print(f"Tabela destino : {TABLE_BRONZE}")
print(f"Volume path    : {VOLUME_PATH}")
print(f"Séries         : {list(SERIES.keys())}")

# COMMAND ----------

# MAGIC ## 2. Ingestão da API BCB

import requests

def fetch_serie(serie_id, data_inicio, data_fim):
    url = BCB_BASE_URL.format(serie_id=serie_id)
    params = {"formato": "json", "dataInicial": data_inicio, "dataFinal": data_fim}
    for tentativa in range(1, 4):
        try:
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[RETRY {tentativa}/3] Série {serie_id}: {e}")
            if tentativa == 3:
                raise
    return []

ingest_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
registros = []

for serie_id, nome in SERIES.items():
    dados = fetch_serie(serie_id, data_inicio, data_fim)
    source_url = BCB_BASE_URL.format(serie_id=serie_id)
    for linha in dados:
        registros.append({
            "data":       linha["data"],
            "valor":      linha["valor"],
            "serie_id":   serie_id,
            "nome_serie": nome,
            "ingest_ts":  ingest_ts,
            "source_url": source_url,
        })
    print(f"[OK] Série {serie_id} ({nome}): {len(dados)} registros")

print(f"\nTotal acumulado: {len(registros)} registros")

# COMMAND ----------

# MAGIC ## 3. Criar tabela Bronze no Unity Catalog (ADR-0007)

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {TABLE_BRONZE} (
    data       STRING    COMMENT 'Data no formato original da API (dd/MM/yyyy)',
    valor      STRING    COMMENT 'Valor da série no formato original da API',
    serie_id   STRING    COMMENT 'Código da série BCB (1, 11 ou 433)',
    nome_serie STRING    COMMENT 'Nome legível da série',
    ingest_ts  STRING    COMMENT 'Timestamp de ingestão (yyyy-MM-dd HH:mm:ss)',
    source_url STRING    COMMENT 'URL de origem dos dados'
)
USING DELTA
LOCATION '{VOLUME_PATH}'
""")

print(f"[OK] Tabela {TABLE_BRONZE} pronta (criada ou já existia)")

# COMMAND ----------

# MAGIC ## 4. MERGE INTO — ingestão incremental e idempotente (ADR-0002)

df_novos = spark.createDataFrame(registros)
df_novos.createOrReplaceTempView("novos_registros")

spark.sql(f"""
MERGE INTO {TABLE_BRONZE} AS destino
USING novos_registros AS origem
ON destino.serie_id = origem.serie_id
AND destino.data = origem.data
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
""")

print("[OK] MERGE INTO concluído")

# COMMAND ----------

# MAGIC ## 5. Validação do resultado

display(spark.sql(f"""
SELECT
    serie_id,
    nome_serie,
    COUNT(*)   AS registros,
    MIN(data)  AS primeiro,
    MAX(data)  AS ultimo
FROM {TABLE_BRONZE}
GROUP BY serie_id, nome_serie
ORDER BY serie_id
"""))
