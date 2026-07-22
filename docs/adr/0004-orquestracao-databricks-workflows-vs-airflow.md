# ADR-0004: Orquestração — Databricks Workflows vs Airflow externo

## Status
Aceito

## Contexto

O pipeline bcb-lakehouse-databricks é composto por 4 notebooks que devem ser executados em sequência com dependência explícita:

```
01_bronze_ingest -> 02_silver_transform -> 03_gold_model -> 04_quality_checks
```

A questão é qual ferramenta orquestra essa sequência, gerencia dependências entre tasks e permite reexecução controlada com parâmetros de data.

O projeto anterior, `bcb-pipeline`, usa **Apache Airflow** como orquestrador externo: DAGs Python definem dependências entre operadores, e o Airflow scheduler dispara e monitora cada task individualmente. Essa abordagem é a referência de comparação para esta decisão.

O Databricks oferece **Workflows** como serviço nativo de orquestração: jobs com múltiplas tasks encadeadas, cada task mapeada para um notebook no Repos, com dependências declaradas e parâmetros passados como job parameters. A definição do job pode ser exportada como JSON para versionamento no repositório.

**Restrição de plataforma relevante:** o Databricks Community Edition **não suporta agendamento automático de jobs** (sem cron triggers ou scheduled runs). Jobs só podem ser disparados manualmente via UI ou via API REST. Além disso, o cluster para automaticamente após 2 horas de inatividade, o que torna o agendamento automático impraticável mesmo que fosse suportado.

## Decisão

Utilizar **Databricks Workflows** como orquestrador nativo do pipeline, com a definição do job versionada em `workflows/bcb_pipeline.json`.

**Estrutura do job:**

| Task | Notebook | Depende de |
|------|----------|-----------|
| `bronze_ingest` | `notebooks/01_bronze_ingest.py` | — (task raiz) |
| `silver_transform` | `notebooks/02_silver_transform.py` | `bronze_ingest` |
| `gold_model` | `notebooks/03_gold_model.py` | `silver_transform` |
| `quality_checks` | `notebooks/04_quality_checks.py` | `gold_model` |

**Parâmetros do job:** `data_inicio` e `data_fim`, passados como job parameters e mapeados para widgets nos notebooks. Valores default: últimos 30 dias.

**Artefato de versionamento:** `workflows/bcb_pipeline.json` contém a definição completa do job exportada da UI do Databricks. Este arquivo é o equivalente funcional dos arquivos de DAG Python do `bcb-pipeline`.

**Execução:** manual via UI do Databricks ou via Databricks CLI (`databricks jobs run-now`). Não há agendamento automático neste projeto — limitação do Community Edition documentada explicitamente.

**Comparação direta com o `bcb-pipeline`:**

| Critério | bcb-pipeline (Airflow) | bcb-lakehouse-databricks (Workflows) |
|----------|----------------------|--------------------------------------|
| Definição do pipeline | DAG Python (`dags/bcb_dag.py`) | JSON exportado (`workflows/bcb_pipeline.json`) |
| Dependências entre tasks | `>>` operator no DAG | `depends_on` no job definition |
| Parâmetros de execução | Airflow Variables / conf dict | Job parameters (widgets) |
| Agendamento | Cron expression na DAG | Manual (Community Edition) / Cron trigger (edições pagas) |
| Monitoramento | Airflow UI (logs por task) | Databricks UI (logs por task run) |
| Reexecução de task isolada | `airflow tasks run` | Re-run de task individual via UI |
| Versionamento da definição | Arquivo Python no repo | JSON exportado no repo |
| Custo de infraestrutura | Instância EC2/ECS para o Airflow | Incluído no Databricks (sem infra separada) |
| Curva de entrada | Alta (setup de ambiente separado) | Baixa (nativo na plataforma) |

## Consequências

### Positivas
- **Zero infraestrutura adicional**: não é necessário provisionar, manter ou monitorar um servidor Airflow separado — o orquestrador está embutido na plataforma Databricks
- **Integração nativa com notebooks e cluster**: cada task do Workflow usa o mesmo cluster e contexto do workspace, sem overhead de comunicação entre serviços
- **Visibilidade unificada**: logs de execução, duração de cada task e status do job estão na mesma UI onde os notebooks são desenvolvidos e testados
- **Definição versionável**: o JSON exportado pelo Databricks pode ser commitado no repositório e reimportado em outro workspace, cumprindo o mesmo papel dos arquivos de DAG no Airflow
- **Demonstração de diferencial de portfólio**: a comparação Airflow vs Workflows, documentada nesta ADR e no `docs/architecture.md`, é o diferencial narrativo central do projeto

### Negativas / Trade-offs
- **Sem agendamento automático no Community Edition**: execução manual é o único modo disponível; em produção com edições pagas, o agendamento por cron seria nativo
- **Dependência de UI para criação do job**: a definição inicial do Workflow é feita pela interface gráfica do Databricks, não por código declarativo (como um DAG Python). O JSON exportado documenta o resultado, mas não é o artefato de criação
- **Portabilidade limitada ao ecossistema Databricks**: o Workflow só funciona dentro do Databricks — ao contrário do Airflow, que pode orquestrar tarefas em qualquer plataforma ou linguagem
- **Sem DAG como código por padrão**: o Airflow representa o pipeline como código Python versionável desde a criação; o Workflow requer a UI como intermediário, e o JSON de exportação é um artefato secundário
- **Reexecução parcial menos granular**: no Airflow é possível reexecutar tasks individuais com backfill complexo via CLI; no Workflow Community Edition, o controle é mais limitado

## Alternativas consideradas

- **Apache Airflow externo (como no `bcb-pipeline`)**: orquestrar os notebooks via Airflow usando o operador `DatabricksRunNowOperator` ou `DatabricksSubmitRunOperator`. Rejeitado porque adiciona uma camada de infraestrutura externa desnecessária para este projeto — o objetivo é demonstrar as capacidades nativas do Databricks, e o Airflow já foi amplamente demonstrado no `bcb-pipeline`.

- **Execução manual sequencial sem orquestrador formal**: rodar os 4 notebooks manualmente na ordem correta sem um job definido. Rejeitado porque não gera o artefato `bcb_pipeline.json` que demonstra conhecimento de Workflows, e não permite passar parâmetros de data de forma controlada.

- **Databricks Asset Bundles (DAB) para definição como código**: usar o CLI da Databricks com arquivos YAML para definir o job como Infrastructure as Code. Rejeitado porque o Community Edition tem suporte limitado a DABs e aumentaria a complexidade de setup além do escopo do projeto.

## Revisão
Elaborado por: Claude (Agente IA) — arquiteto-dados-aws
Data/hora: 2026-07-22 00:20 BRT

## Aprovação
Aprovado por: Lucas de Araújo
Data/hora: 2026-07-22 00:53 BRT
