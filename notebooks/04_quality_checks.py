# Databricks notebook source
# MAGIC # Quality Checks  - bcb-lakehouse-databricks
# MAGIC
# MAGIC Validações de qualidade cobrindo as camadas Bronze, Silver e Gold.
# MAGIC Implementadas como assertions Python nativas com mensagens descritivas (ADR-0005).
# MAGIC
# MAGIC Cada assertion lança exceção com formato:
# MAGIC `[FALHA] {contexto}: {o que foi verificado}. Encontrado: {valor}. Esperado: {esperado}.`
# MAGIC
# MAGIC **ADR que governa este notebook:** ADR-0005

# COMMAND ----------

#Configuração

CATALOG = "bcb_lakehouse_databricks"
SCHEMA = "default"
TABLE_BRONZE = f"{CATALOG}.{SCHEMA}.bronze_bcb"
TABLE_SILVER = f"{CATALOG}.{SCHEMA}.silver_bcb"
TABLE_FCT = f"{CATALOG}.{SCHEMA}.fct_indicadores"
TABLE_DIM = f"{CATALOG}.{SCHEMA}.dim_data"

verificacoes_ok = 0
verificacoes_falha = 0

def checar(condicao, contexto, encontrado, esperado):
    global verificacoes_ok, verificacoes_falha
    if not condicao:
        verificacoes_falha += 1
        raise AssertionError(
            f"[FALHA] {contexto}: Encontrado: {encontrado}. Esperado: {esperado}."
        )
    verificacoes_ok += 1
    print(f"[OK] {contexto}")

print(f"Tabelas: {TABLE_BRONZE}, {TABLE_SILVER}, {TABLE_FCT}, {TABLE_DIM}")

# COMMAND ----------

#Validações Bronze

# Assert 1  - Nenhum ingest_ts nulo
nulos_ts = spark.sql(f"SELECT COUNT(*) AS n FROM {TABLE_BRONZE} WHERE ingest_ts IS NULL").collect()[0]["n"]
checar(nulos_ts == 0, "Bronze: ausência de ingest_ts nulo", nulos_ts, 0)

# Assert 2  - Nenhum serie_id nulo
nulos_sid = spark.sql(f"SELECT COUNT(*) AS n FROM {TABLE_BRONZE} WHERE serie_id IS NULL").collect()[0]["n"]
checar(nulos_sid == 0, "Bronze: ausência de serie_id nulo", nulos_sid, 0)

# Assert 3  - As 3 séries estão presentes
series = [r["serie_id"] for r in spark.sql(f"SELECT DISTINCT serie_id FROM {TABLE_BRONZE} ORDER BY serie_id").collect()]
checar(set(series) == {"1", "11", "433"}, "Bronze: 3 séries presentes (1, 11, 433)", series, ["1", "11", "433"])

# COMMAND ----------

#Validações Silver

# Assert 4  - Zero valores nulos
nulos_valor = spark.sql(f"SELECT COUNT(*) AS n FROM {TABLE_SILVER} WHERE valor IS NULL").collect()[0]["n"]
checar(nulos_valor == 0, "Silver: zero valores nulos", nulos_valor, 0)

# Assert 5  - Zero duplicatas por (serie_id, data)
total = spark.sql(f"SELECT COUNT(*) AS n FROM {TABLE_SILVER}").collect()[0]["n"]
distintos = spark.sql(f"SELECT COUNT(*) AS n FROM (SELECT DISTINCT serie_id, data FROM {TABLE_SILVER})").collect()[0]["n"]
checar(total == distintos, "Silver: sem duplicatas (serie_id, data)", f"{total} linhas vs {distintos} distintos", "total == distintos")

# Assert 6  - Selic entre 0.01 e 50.0
selic_fora = spark.sql(f"SELECT COUNT(*) AS n FROM {TABLE_SILVER} WHERE serie_id = '11' AND (valor < 0.01 OR valor > 50.0)").collect()[0]["n"]
checar(selic_fora == 0, "Silver: Selic no range [0.01, 50.0]", selic_fora, 0)

# Assert 7  - IPCA entre -5.0 e 30.0
ipca_fora = spark.sql(f"SELECT COUNT(*) AS n FROM {TABLE_SILVER} WHERE serie_id = '433' AND (valor < -5.0 OR valor > 30.0)").collect()[0]["n"]
checar(ipca_fora == 0, "Silver: IPCA no range [-5.0, 30.0]", ipca_fora, 0)

# Assert 8  - USD/BRL entre 1.0 e 20.0
usd_fora = spark.sql(f"SELECT COUNT(*) AS n FROM {TABLE_SILVER} WHERE serie_id = '1' AND (valor < 1.0 OR valor > 20.0)").collect()[0]["n"]
checar(usd_fora == 0, "Silver: USD/BRL no range [1.0, 20.0]", usd_fora, 0)

# Assert 9  - Tipos corretos
tipo_valor = spark.sql(f"SELECT typeof(valor) AS t FROM {TABLE_SILVER} LIMIT 1").collect()[0]["t"]
checar(tipo_valor == "double", "Silver: tipo de valor é double", tipo_valor, "double")

tipo_data = spark.sql(f"SELECT typeof(data) AS t FROM {TABLE_SILVER} LIMIT 1").collect()[0]["t"]
checar(tipo_data == "date", "Silver: tipo de data é date", tipo_data, "date")

# COMMAND ----------

#Validações Gold

# Assert 10  - fct_indicadores tem registros
total_fct = spark.sql(f"SELECT COUNT(*) AS n FROM {TABLE_FCT}").collect()[0]["n"]
checar(total_fct > 0, "Gold: fct_indicadores tem registros", total_fct, "> 0")

# Assert 11  - Nenhuma data nula em fct_indicadores
nulos_data = spark.sql(f"SELECT COUNT(*) AS n FROM {TABLE_FCT} WHERE data IS NULL").collect()[0]["n"]
checar(nulos_data == 0, "Gold: sem datas nulas em fct_indicadores", nulos_data, 0)

# Assert 12  - dim_data cobre 100% das datas de fct_indicadores
datas_sem_dim = spark.sql(f"""
    SELECT COUNT(*) AS n FROM {TABLE_FCT} f
    LEFT JOIN {TABLE_DIM} d ON f.data = d.data
    WHERE d.data IS NULL
""").collect()[0]["n"]
checar(datas_sem_dim == 0, "Gold: dim_data cobre 100% das datas de fct_indicadores", datas_sem_dim, 0)

# Assert 13  - dim_data sem duplicatas por data
total_dim = spark.sql(f"SELECT COUNT(*) AS n FROM {TABLE_DIM}").collect()[0]["n"]
distintos_dim = spark.sql(f"SELECT COUNT(DISTINCT data) AS n FROM {TABLE_DIM}").collect()[0]["n"]
checar(total_dim == distintos_dim, "Gold: dim_data sem duplicatas por data", f"{total_dim} vs {distintos_dim}", "total == distintos")

# Assert 14  - fct_indicadores sem duplicatas por data
total_fct2 = spark.sql(f"SELECT COUNT(*) AS n FROM {TABLE_FCT}").collect()[0]["n"]
distintos_fct = spark.sql(f"SELECT COUNT(DISTINCT data) AS n FROM {TABLE_FCT}").collect()[0]["n"]
checar(total_fct2 == distintos_fct, "Gold: fct_indicadores sem duplicatas por data", f"{total_fct2} vs {distintos_fct}", "total == distintos")

# COMMAND ----------

#Sumário

total = verificacoes_ok + verificacoes_falha
if verificacoes_falha == 0:
    print(f"Todas as {total} verificações passaram.")
else:
    raise AssertionError(f"{verificacoes_falha} de {total} verificações falharam.")
