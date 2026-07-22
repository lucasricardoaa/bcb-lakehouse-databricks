# Databricks notebook source
# MAGIC # Setup Validation — bcb-lakehouse-databricks
# MAGIC Notebook temporário para validar o ambiente. Executar célula a célula.
# MAGIC Pode ser deletado após a Fase 2 estar concluída.

# COMMAND ----------

# MAGIC ## 1. Teste de conectividade — API do Banco Central

import requests

url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados?formato=json&dataInicial=01/01/2026&dataFinal=31/01/2026"

try:
    response = requests.get(url, timeout=10)
    assert response.status_code == 200, f"Status inesperado: {response.status_code}"
    dados = response.json()
    print(f"[OK] API BCB acessível. Status: {response.status_code}")
    print(f"[OK] Primeiros registros: {dados[:3]}")
except Exception as e:
    print(f"[FALHA] {e}")

# COMMAND ----------

# MAGIC ## 2. Criar Volumes no Unity Catalog (ADR-0006)

spark.sql("CREATE VOLUME IF NOT EXISTS bcb_lakehouse_databricks.default.bronze")
print("[OK] Volume criado (ou já existia): bcb_lakehouse_databricks.default.bronze")

spark.sql("CREATE VOLUME IF NOT EXISTS bcb_lakehouse_databricks.default.silver")
print("[OK] Volume criado (ou já existia): bcb_lakehouse_databricks.default.silver")

spark.sql("CREATE VOLUME IF NOT EXISTS bcb_lakehouse_databricks.default.gold")
print("[OK] Volume criado (ou já existia): bcb_lakehouse_databricks.default.gold")

print("\nVolumes disponíveis em bcb_lakehouse_databricks.default:")
display(spark.sql("SHOW VOLUMES IN bcb_lakehouse_databricks.default"))

# COMMAND ----------

# MAGIC ## 3. Verificar Delta Lake

from delta.tables import DeltaTable
import pyspark

print(f"[OK] Spark versão: {spark.version}")
print(f"[OK] Delta Lake disponível")

# COMMAND ----------

# MAGIC ## Resultado
# MAGIC Se todas as células acima executaram sem erro, a Fase 2 está concluída.
# MAGIC Este notebook pode ser deletado.
