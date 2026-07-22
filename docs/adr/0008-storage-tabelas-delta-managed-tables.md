# ADR-0008: Storage de tabelas Delta — tabelas gerenciadas do Unity Catalog em substituição a tabelas externas com LOCATION em Volume

## Status
Aceito

## Contexto

A ADR-0007 decidiu usar **tabelas externas** no Unity Catalog, com a cláusula `LOCATION` apontando para os caminhos de Volume definidos pela ADR-0006:

```sql
CREATE TABLE IF NOT EXISTS bcb_lakehouse_databricks.default.bronze_bcb
USING DELTA
LOCATION '/Volumes/bcb_lakehouse_databricks/default/bronze/bcb/'
```

Durante a execução do notebook `01_bronze_ingest.py`, esse comando retornou o seguinte erro:

```
INVALID_PARAMETER_VALUE: Missing cloud file system scheme
```

O erro ocorre porque o Unity Catalog, ao processar a cláusula `LOCATION` de uma tabela externa, exige um esquema de cloud storage real — `abfss://` (Azure Data Lake Storage Gen2), `s3://` (Amazon S3) ou `gs://` (Google Cloud Storage). O caminho `/Volumes/...` é uma abstração de acesso a arquivos gerenciada pelo Unity Catalog e **não é reconhecido como esquema de cloud storage** para fins de localização de tabelas externas.

### Diferença entre Volumes e managed tables no Unity Catalog

O Unity Catalog oferece dois mecanismos distintos de persistência dentro da mesma hierarquia `catalog > schema`:

| Mecanismo | Finalidade | Acesso | Gerenciamento de storage |
|-----------|-----------|--------|--------------------------|
| **Volume** | Armazenamento de arquivos arbitrários (CSV, JSON, Parquet bruto, notebooks, modelos) | `/Volumes/<catalog>/<schema>/<volume>/` | O usuário controla o conteúdo do diretório |
| **Managed table** | Armazenamento de tabelas Delta registradas no catálogo | `<catalog>.<schema>.<table>` | O Unity Catalog gerencia o storage no ADLS Gen2 configurado no workspace |

Volumes e tabelas gerenciadas são objetos complementares dentro do Unity Catalog, mas com finalidades diferentes. Um Volume não pode ser usado como `LOCATION` de uma tabela externa porque não é um endpoint de cloud storage — é uma abstração de acesso a arquivos que internamente aponta para um diretório no ADLS Gen2 do workspace, mas essa URI interna não é exposta à cláusula `LOCATION`.

Tabelas gerenciadas (`CREATE TABLE ... USING DELTA` sem `LOCATION`) têm o storage gerenciado automaticamente pelo Unity Catalog no ADLS Gen2 configurado no workspace. O caminho físico é determinado pelo Unity Catalog e não precisa ser especificado pelo usuário.

### Situação do projeto

Os Volumes `bronze`, `silver` e `gold` foram criados no setup do workspace e estão disponíveis no catálogo `bcb_lakehouse_databricks`, schema `default`. Eles permanecem funcionais para acesso a arquivos arbitrários (ex: upload de CSVs, leitura de arquivos brutos via `dbutils.fs`), mas não são utilizados como `LOCATION` de tabelas Delta.

O pipeline pode usar tabelas gerenciadas sem qualquer dependência de caminhos de Volume — o Unity Catalog resolve o storage automaticamente.

## Decisão

Adotar **tabelas gerenciadas do Unity Catalog** (sem cláusula `LOCATION`) para todas as camadas do pipeline:

**Bronze e Silver — DDL:**

```sql
CREATE TABLE IF NOT EXISTS bcb_lakehouse_databricks.default.bronze_bcb
USING DELTA
-- sem LOCATION
```

**Gold — escrita via PySpark:**

```python
# Em vez de .save(PATH), usar .saveAsTable(TABLE_NAME)
df.write.format("delta") \
    .mode("overwrite") \
    .saveAsTable("bcb_lakehouse_databricks.default.fct_indicadores")
```

O Unity Catalog gerencia o storage de cada tabela no ADLS Gen2 configurado no workspace do Azure Databricks Trial. Nenhum Volume é usado como localização de tabela Delta. Os Volumes criados no setup (`bronze`, `silver`, `gold`) permanecem disponíveis no workspace para outros usos de file storage, mas estão fora do escopo do pipeline de tabelas Delta.

## Consequências

### Positivas
- Elimina o erro `INVALID_PARAMETER_VALUE: Missing cloud file system scheme` que bloqueava a execução do pipeline
- Sintaxe mais simples: `CREATE TABLE IF NOT EXISTS ... USING DELTA` sem necessidade de gerenciar caminhos de storage
- O Unity Catalog garante consistência entre o registro lógico da tabela e seu storage físico — não há risco de divergência entre Volume e tabela como havia com tabelas externas
- Storage provisionado automaticamente pelo Unity Catalog no ADLS Gen2 do workspace, sem necessidade de configuração adicional
- Compatível com a hierarquia de nomes totalmente qualificados definida pela ADR-0007 (`bcb_lakehouse_databricks.default.<nome_tabela>`) — apenas a cláusula `LOCATION` é removida
- Reprodução simplificada: novos workspaces do Azure Databricks Trial que sigam o mesmo setup conseguem executar o pipeline sem criar Volumes previamente

### Negativas / Trade-offs
- **Risco de perda de dados em DROP TABLE**: tabelas gerenciadas têm o storage deletado automaticamente quando a tabela é removida do catálogo. Com tabelas externas (padrão rejeitado da ADR-0007), os arquivos no Volume sobrevivem a um `DROP TABLE`. Este trade-off foi considerado e rejeitado na ADR-0007 — porém, dado que o projeto roda em ambiente Trial com cluster efêmero, o risco de perda de dados já existe independentemente da estratégia de storage. A recriação das tabelas via reexecução do pipeline é o mecanismo de recuperação esperado neste contexto.
- O caminho físico no ADLS Gen2 é gerenciado pelo Unity Catalog e não é visível nem configurável pelo usuário — isso reduz o controle sobre o layout de storage, o que é aceitável para um projeto de portfólio mas seria um trade-off relevante em ambiente corporativo com requisitos de organização de storage explícita
- Os caminhos de Volume referenciados na ADR-0006 e na ADR-0007 (tabela de mapeamento `Volume de storage`) não são mais utilizados pelo pipeline — parte da documentação anterior fica desatualizada e requer a presente ADR para referência

## Alternativas consideradas

- **Tabelas externas com URI do ADLS Gen2 explícita (`abfss://`)**: usar o endpoint ADLS Gen2 real do workspace como `LOCATION` (`abfss://<container>@<storage_account>.dfs.core.windows.net/...`). Rejeitado porque requer descoberta manual da URI do ADLS Gen2 provisionado automaticamente pelo Trial (não exposta na UI de forma direta), adiciona acoplamento ao storage account específico do workspace e não oferece vantagem funcional sobre tabelas gerenciadas neste contexto.

- **Reescrever os arquivos Delta no Volume e referenciar por caminho direto nas queries** (`delta.\`/Volumes/...\``): usar Volumes para persistência e referenciar as tabelas por caminho em vez de por nome lógico. Rejeitado pelos mesmos motivos da ADR-0003 e ADR-0007: queries verbosas, acoplamento ao caminho físico, perda de nome lógico para `DESCRIBE HISTORY` e `DESCRIBE DETAIL`, e o erro original evidencia que Volumes não funcionam como `LOCATION` de tabelas externas de qualquer forma.

## Relação com outras ADRs

- **ADR-0006**: esta ADR substitui parcialmente a ADR-0006. A decisão de usar Volumes como `LOCATION` das tabelas Delta externas é inviável tecnicamente — Volumes não são aceitos como esquema de cloud storage pela cláusula `LOCATION`. Os Volumes criados no setup permanecem válidos como objetos de file storage do Unity Catalog, mas estão fora do escopo do pipeline de tabelas Delta. O restante da ADR-0006 (adoção do Unity Catalog como modelo de storage e governança em substituição ao DBFS) permanece válido e não é afetado.
- **ADR-0007**: esta ADR substitui parcialmente a ADR-0007 no que diz respeito ao tipo de tabela. A ADR-0007 rejeitou tabelas gerenciadas pelo risco de `DROP TABLE` apagar o storage; a presente ADR reconsiderou esse trade-off diante da inviabilidade técnica das tabelas externas com `LOCATION` em Volume. A convenção de nomes totalmente qualificados (`bcb_lakehouse_databricks.default.<nome_tabela>`) definida pela ADR-0007 permanece inalterada.

## Revisão
Elaborado por: Claude (Agente IA) — arquiteto-dados
Data/hora: 2026-07-22 18:21 BRT

## Aprovação
Aprovado por: Lucas de Araújo
Data/hora: 2026-07-22 BRT
