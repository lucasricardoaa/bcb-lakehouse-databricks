# ADR-0003: Registro de tabelas — Hive Metastore vs caminhos DBFS absolutos

## Status
Substituído por ADR-0007

## Contexto

A ADR-0001 definiu que os dados serão armazenados no DBFS com caminhos absolutos (`/delta/bronze/bcb/`, `/delta/silver/bcb/`, `/delta/gold/`). A questão subsequente é: como os notebooks referenciam essas tabelas nas queries SQL e operações PySpark?

Há duas abordagens possíveis:

**Abordagem A — Caminhos absolutos diretos em toda query:**
```sql
SELECT * FROM delta.`/delta/silver/bcb/`
SELECT COUNT(*) FROM delta.`/delta/gold/fct_indicadores`
```

**Abordagem B — Registro no Hive Metastore com nome lógico:**
```python
spark.sql("CREATE TABLE IF NOT EXISTS silver_bcb USING DELTA LOCATION '/delta/silver/bcb/'")
```
```sql
SELECT * FROM silver_bcb
SELECT COUNT(*) FROM fct_indicadores
```

O Hive Metastore é o catálogo de metadados padrão do Databricks (e do Spark em geral), disponível em todas as edições incluindo o Community Edition. Ele mantém o mapeamento entre nome lógico de tabela e caminho físico no storage, permitindo referência por nome em queries SQL.

No contexto do `bcb-pipeline` (Projeto 1), o equivalente é o AWS Glue Data Catalog, que mapeia tabelas Athena para arquivos Parquet no S3. O Hive Metastore cumpre a mesma função no ecossistema Databricks/Spark.

## Decisão

Registrar todas as tabelas Delta no **Hive Metastore local do workspace** como tabelas externas (`EXTERNAL TABLE`) com localização explícita no DBFS.

**Convenção de nomes lógicos:**

| Camada | Nome lógico no Metastore | Caminho DBFS (ADR-0001) |
|--------|--------------------------|------------------------|
| Bronze | `bronze_bcb` | `/delta/bronze/bcb/` |
| Silver | `silver_bcb` | `/delta/silver/bcb/` |
| Gold — fato | `fct_indicadores` | `/delta/gold/fct_indicadores/` |
| Gold — dimensão | `dim_data` | `/delta/gold/dim_data/` |

**Responsabilidade de registro:** cada notebook registra sua própria tabela de saída após a primeira escrita. O registro usa `CREATE TABLE IF NOT EXISTS` para ser idempotente.

**Padrão de registro:**
```python
spark.sql("""
    CREATE TABLE IF NOT EXISTS {nome_logico}
    USING DELTA
    LOCATION '{caminho_dbfs}'
""")
```

**Escopo do Metastore:** o Hive Metastore do Community Edition é local ao workspace. Os registros não persistem se o workspace for recriado, mas os dados no DBFS permanecem. O procedimento de recuperação é reexecutar o bloco `CREATE TABLE IF NOT EXISTS` de cada notebook.

## Consequências

### Positivas
- Queries SQL usam nomes legíveis (`SELECT * FROM silver_bcb`) em vez de caminhos com backticks (`SELECT * FROM delta.\`/delta/silver/bcb/\``)
- `DESCRIBE HISTORY silver_bcb` e `DESCRIBE DETAIL silver_bcb` funcionam por nome lógico, facilitando auditoria e exploração interativa nos notebooks
- Compatível com o padrão SQL padrão — qualquer ferramenta que conecte via JDBC/ODBC ao Databricks pode referenciar as tabelas pelo nome
- Separa o nome lógico (estável) do caminho físico (implementação) — mudança de caminho no DBFS exige apenas um `ALTER TABLE ... SET LOCATION`, não alterações em todos os notebooks
- Analogia direta com o Glue Data Catalog do `bcb-pipeline`, tornando a comparação entre projetos concreta e didática

### Negativas / Trade-offs
- **Metastore local ao workspace**: os registros de nome lógico não persistem entre workspaces diferentes. Em caso de recriação do workspace, os dados no DBFS estão intactos, mas é necessário reexecutar os blocos de registro de tabela em cada notebook antes de usar queries SQL por nome
- **Sem Unity Catalog**: o Hive Metastore não oferece controle de acesso por tabela, linhagem automática ou governança centralizada — limitação herdada da plataforma Community Edition (documentada na ADR-0001)
- **Possível conflito de nome**: se o mesmo workspace for usado para outros projetos, nomes como `bronze_bcb` podem colidir. Mitigação: prefixar com o nome do projeto se necessário (`bcb_bronze`, `bcb_silver`)

## Alternativas consideradas

- **Referenciar sempre por caminho absoluto (`delta.\`/path/\``)**: evita dependência do Metastore. Rejeitado porque torna as queries verbosas e acopladas ao caminho físico — qualquer reorganização do DBFS exige atualização em todos os notebooks e queries.

- **Unity Catalog com esquemas e catálogos hierárquicos (`catalog.schema.table`)**: modelo preferido para produção Databricks, com isolamento por namespace e controle de acesso. Rejeitado porque **não está disponível no Databricks Community Edition** — restrição documentada na ADR-0001.

- **Usar apenas a API PySpark (`spark.read.format("delta").load(path)`) sem SQL nomeado**: manter todo o acesso via código Python, sem registro no Metastore. Rejeitado porque perde a capacidade de usar SQL puro nos notebooks de exploração e nos quality checks, e impossibilita `DESCRIBE HISTORY` por nome lógico.

## Relação com outras ADRs

- **ADR-0001** (Armazenamento Delta): define os caminhos DBFS absolutos que esta ADR registra como nomes lógicos no Hive Metastore. As duas decisões são complementares e devem ser lidas em conjunto.

## Revisão
Elaborado por: Claude (Agente IA) — arquiteto-dados-aws
Data/hora: 2026-07-22 00:20 BRT

## Aprovação
Aprovado por: Lucas de Araújo
Data/hora: 2026-07-22 00:53 BRT
