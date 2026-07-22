# ADR-0001: Armazenamento Delta — DBFS vs Unity Catalog

## Status
Substituído por ADR-0006

## Contexto

O projeto bcb-lakehouse-databricks implementa uma arquitetura medallion (Bronze → Silver → Gold) sobre Delta Lake no Databricks Community Edition. A primeira decisão estrutural é onde as tabelas Delta serão armazenadas e como os caminhos serão gerenciados entre os notebooks.

O Databricks oferece dois modelos de armazenamento e governança:

- **DBFS (Databricks File System)**: sistema de arquivos nativo, disponível em todas as edições, com caminhos absolutos do tipo `/delta/bronze/...`. Não oferece controle de acesso por catálogo nem auditoria centralizada.
- **Unity Catalog**: plano de governança unificado da Databricks com catálogo hierárquico (`catalog.schema.table`), controle de acesso baseado em roles, auditoria e linhagem de dados. Disponível apenas nas edições pagas (Standard, Premium, Enterprise).

O Databricks Community Edition, plataforma escolhida para este projeto, **não suporta Unity Catalog**. Essa restrição é uma limitação de plataforma, não uma escolha de design, e deve ser documentada explicitamente para contextualização em portfólio.

O projeto anterior na stack AWS (`bcb-pipeline`) utiliza S3 com particionamento Hive-style e Athena para query. A decisão de armazenamento aqui é o equivalente funcional dessa escolha, e a comparação entre as duas abordagens é o diferencial narrativo deste projeto.

## Decisão

Utilizar **DBFS com caminhos absolutos** para armazenamento das tabelas Delta, organizados por camada:

```
/delta/bronze/bcb/{serie_id}/
/delta/silver/bcb/
/delta/gold/
```

Os caminhos absolutos serão definidos como variáveis de configuração em um arquivo compartilhado, **nunca como literais inline em cada notebook**. Todos os notebooks importam essas variáveis para garantir consistência.

A estrutura de camadas adota a convenção `medallion`:

| Camada | Caminho DBFS | Conteúdo |
|--------|-------------|----------|
| Bronze | `/delta/bronze/bcb/{serie_id}/` | JSON bruto da API BCB, sem transformação |
| Silver | `/delta/silver/bcb/` | Dados limpos, tipados, particionados por `ano` e `mes` |
| Gold   | `/delta/gold/` | Modelo analítico (`fct_indicadores`, `dim_data`) |

Esta decisão é complementada pela ADR-0003, que define como as tabelas serão registradas no Hive Metastore para permitir queries SQL por nome lógico sem uso de caminhos absolutos.

## Consequências

### Positivas
- Compatível com Databricks Community Edition sem restrições
- Caminhos DBFS persistem entre reinicializações de cluster (o dado não se perde quando o cluster para por inatividade)
- Estrutura análoga ao particionamento Hive-style do S3 no `bcb-pipeline`, tornando a comparação entre projetos direta e didática
- Configuração centralizada de caminhos elimina inconsistências entre notebooks
- Delta Lake sobre DBFS oferece ACID, time travel e schema enforcement independentemente do Unity Catalog

### Negativas / Trade-offs
- **Sem governança centralizada de dados**: não há controle de acesso por tabela, auditoria de queries ou linhagem automática — recursos disponíveis apenas com Unity Catalog
- **Sem isolamento de workspace**: os dados em DBFS são acessíveis a qualquer usuário do mesmo workspace, sem segregação por role
- **Portabilidade limitada**: caminhos DBFS absolutos são específicos do workspace; mover para outro workspace requer recriar os dados ou ajustar todos os caminhos
- **Diferença relevante para produção**: em um ambiente Enterprise, a decisão seria Unity Catalog — este projeto documenta essa diferença explicitamente para fins de portfólio

## Alternativas consideradas

- **Unity Catalog**: modelo de governança preferido para ambientes de produção Databricks. Oferece catálogo hierárquico, controle de acesso granular e linhagem de dados. Rejeitado porque **não está disponível no Databricks Community Edition**, que é a plataforma deste projeto.

- **S3 externo como storage para Delta**: montar um bucket S3 no DBFS via `dbutils.fs.mount()` e armazenar os arquivos Delta lá. Rejeitado porque requer credenciais AWS configuradas no workspace, adiciona complexidade de infraestrutura ao projeto e foge do escopo de demonstração das capacidades nativas do Databricks.

- **Armazenamento em formato Parquet sem Delta**: usar `spark.write.parquet()` diretamente no DBFS, sem Delta Lake. Rejeitado porque perde as garantias ACID, time travel e schema enforcement que são o diferencial central deste projeto em relação ao `bcb-pipeline`.

## Relação com outras ADRs

- **ADR-0003** (Registro de tabelas): complementa esta decisão definindo como os caminhos DBFS decididos aqui são expostos como nomes lógicos no Hive Metastore, permitindo `SELECT * FROM silver_bcb` em vez de referenciar o caminho absoluto diretamente.

## Revisão
Elaborado por: Claude (Agente IA) — arquiteto-dados-aws
Data/hora: 2026-07-22 00:20 BRT

## Aprovação
Aprovado por: Lucas de Araújo
Data/hora: 2026-07-22 00:53 BRT
