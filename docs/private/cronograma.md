# Cronograma de Desenvolvimento — bcb-lakehouse-databricks

> Estimativa total: ~16h | 9 sessoes
> Plataforma: Databricks Community Edition
> Nota: este cronograma nao define datas. Define sequencia, dependencias e criterios de conclusao.

---

## Principio de governanca

**Nenhum notebook e implementado antes da ADR que governa sua decisao central ser criada e aceita.**

ADRs sao entregaveis de fase, nao documentacao retroativa. O ciclo e sempre:
`decisao identificada -> ADR redigida -> ADR aceita -> implementacao autorizada`

---

## Visao geral das fases

| Fase | Sessoes | Horas est. | Entregavel principal | ADRs criadas nesta fase |
|------|---------|------------|----------------------|-------------------------|
| 0 — Governanca | 1 | 1h | ADR-0000 (convencoes) + estrutura do repositorio | ADR-0000 |
| 1 — Decisoes de arquitetura | 1 | 2h | ADR-0001 a ADR-0005 aceitas | ADR-0001, ADR-0002, ADR-0003, ADR-0004, ADR-0005 |
| 2 — Setup do ambiente | 1 | 1h | Cluster, Repos e conectividade validados | — |
| 3 — Bronze | 1 | 2h | Notebook `01_bronze_ingest.py` funcionando | — |
| 4 — Silver | 1 | 2.5h | Notebook `02_silver_transform.py` com MERGE e constraints | — |
| 5 — Gold | 1 | 2.5h | Notebook `03_gold_model.py` com `fct_indicadores` + `dim_data` | — |
| 6 — Quality | 1 | 2h | Notebook `04_quality_checks.py` com 10+ assertions | — |
| 7 — Workflow | 1 | 2h | Job Databricks encadeado + `workflows/bcb_pipeline.json` | — |
| 8 — Docs e revisao | 1 | 1h | README publicavel + `architecture.md` + revisao final | — |

**Total: ~16h em 9 sessoes**

---

## Catalogo de ADRs do projeto

| ADR | Titulo | Fase de criacao | Bloqueia |
|-----|--------|-----------------|----------|
| ADR-0000 | Convencoes de ADR deste projeto | Fase 0 | Todas as demais ADRs |
| ADR-0001 | Estrategia de armazenamento Delta: DBFS vs Unity Catalog | Fase 1 | Fases 3, 4, 5 |
| ADR-0002 | Estrategia de ingestao incremental: MERGE INTO vs INSERT OVERWRITE | Fase 1 | Fases 3, 4 |
| ADR-0003 | Registro de tabelas: Hive Metastore vs caminhos DBFS absolutos | Fase 1 | Fases 3, 4, 5, 6 |
| ADR-0004 | Orquestracao: Databricks Workflows vs Airflow externo | Fase 1 | Fase 7 |
| ADR-0005 | Validacao de qualidade: assertions Python vs framework externo | Fase 1 | Fase 6 |

---

## Dependencias entre entregas

```
Fase 0 (ADR-0000 + estrutura)
    |
    v
Fase 1 (ADR-0001 a ADR-0005 aceitas)
    |
    v
Fase 2 (Setup do ambiente)
    |
    v
Fase 3 (Bronze) <-- requer ADR-0001, ADR-0002, ADR-0003
    |
    v
Fase 4 (Silver) <-- requer ADR-0001, ADR-0002, ADR-0003
    |
    v
Fase 5 (Gold) --------+
    |                  |
    v                  v
Fase 6 (Quality)   Fase 7 (Workflow) <-- requer ADR-0004
    |                  |
    +-------+----------+
            |
            v
      Fase 8 (Docs e revisao)
```

Regras de bloqueio:
- A Fase 1 nao pode iniciar enquanto ADR-0000 nao estiver aceita
- As Fases 3, 4 e 5 nao podem iniciar enquanto ADR-0001, ADR-0002 e ADR-0003 nao estiverem aceitas
- A Fase 7 nao pode iniciar enquanto ADR-0004 nao estiver aceita e os notebooks das Fases 3-6 estiverem prontos
- A Fase 8 so inicia quando as Fases 6 e 7 estiverem concluidas

---

## Sessao 0 — Governanca e estrutura do repositorio (1h)

**Objetivo:** Estabelecer as convencoes de ADR do projeto e criar a estrutura de diretorios antes de qualquer codigo.

### Entregavel obrigatorio: ADR-0000

Criar `docs/adr/ADR-0000-convencoes-adr.md` com:
- Formato padrao de ADR adotado no projeto
- Onde os ADRs sao armazenados (`docs/adr/`)
- Numeracao: quatro digitos, zero-padded (ADR-0001, ADR-0002...)
- Estados validos: Proposto | Aceito | Deprecado | Substituido por ADR-NNNN
- Regra: nenhuma implementacao ocorre antes da ADR que a governa estar com status "Aceito"

### Tarefas restantes
1. Criar estrutura de diretorios do repositorio conforme documento de concepcao:
   ```
   notebooks/
   workflows/
   docs/
   docs/adr/
   README.md (placeholder)
   ```
2. Adicionar `.gitignore` com exclusoes padrao para Databricks (arquivos `.python`, caches locais)

### Criterio de conclusao ("done")
- `docs/adr/ADR-0000-convencoes-adr.md` existe, esta completo e com status "Aceito"
- Estrutura de diretorios criada no repositorio GitHub
- Nenhum notebook criado ainda

---

## Sessao 1 — Decisoes de arquitetura (2h)

**Objetivo:** Registrar e aceitar todas as ADRs que governam as escolhas tecnicas centrais do projeto. Nenhuma linha de codigo de pipeline e escrita nesta sessao.

### ADR-0001 — Estrategia de armazenamento Delta: DBFS vs Unity Catalog

**Questao central:** onde armazenar as tabelas Delta no Databricks Community Edition?

**Decisao esperada:** DBFS com caminhos absolutos (`/delta/bronze/`, `/delta/silver/`, `/delta/gold/`), pois o Community Edition nao suporta Unity Catalog. Documentar essa limitacao como diferenca relevante em relacao ao ambiente Enterprise.

**Consequencias a registrar:** sem governanca centralizada de dados; acesso por caminho absoluto em todos os notebooks; necessidade de Hive Metastore para queries SQL sem path (ver ADR-0003).

---

### ADR-0002 — Estrategia de ingestao incremental: MERGE INTO vs INSERT OVERWRITE

**Questao central:** como garantir idempotencia na ingestao das series historicas da API BCB?

**Decisao esperada:** MERGE INTO para execucoes incrementais (chave: `serie_id + data`), com INSERT OVERWRITE apenas para o backfill inicial de historico. Documentar o trade-off de performance para volumes grandes vs a garantia de idempotencia.

**Consequencias a registrar:** notebooks precisam de parametros de janela de datas (widgets); execucoes repetidas com a mesma janela nao duplicam registros; backfill inicial usa estrategia diferente e deve ser documentado como caso especial.

---

### ADR-0003 — Registro de tabelas: Hive Metastore vs caminhos DBFS absolutos

**Questao central:** como referenciar as tabelas Delta nas queries SQL dentro dos notebooks?

**Decisao esperada:** registrar as tabelas no Hive Metastore local do workspace para permitir `SELECT * FROM silver_bcb` em vez de `SELECT * FROM delta./delta/silver/bcb/`. Documentar que o Hive Metastore e local ao workspace e nao persiste entre workspaces distintos.

**Consequencias a registrar:** notebooks de transformacao usam nomes logicos de tabela; o notebook Bronze deve registrar a tabela apos a primeira carga; `DESCRIBE HISTORY nome_logico` funciona normalmente.

---

### ADR-0004 — Orquestracao: Databricks Workflows vs Airflow externo

**Questao central:** como encadear os 4 notebooks em um pipeline executavel de ponta a ponta?

**Decisao esperada:** Databricks Workflows (nativo), exportado como JSON para versionamento. Documentar as limitacoes do Community Edition (sem agendamento automatico, cluster para apos 2h de inatividade) e a comparacao com o Airflow do Projeto 1 (bcb-pipeline).

**Consequencias a registrar:** dependencia de UI do Databricks para criacao e execucao do job; parametros de data passados como job parameters; arquivo `workflows/bcb_pipeline.json` e o artefato de versionamento do pipeline.

---

### ADR-0005 — Validacao de qualidade: assertions Python vs framework externo

**Questao central:** como implementar quality checks sem Great Expectations ou Soda, dado o ambiente Community Edition?

**Decisao esperada:** assertions Python nativas com mensagens descritivas (o que falhou, valor encontrado vs. esperado), complementadas por Delta constraints (`ADD CONSTRAINT`). Documentar a comparacao com Great Expectations usado no Projeto 1.

**Consequencias a registrar:** sem relatorio HTML de qualidade; assertions sao codigo Python puro, mais simples de manter; falhas sao excecoes que interrompem o job no Workflow.

---

### Criterio de conclusao ("done") — Sessao 1
- `docs/adr/ADR-0001-armazenamento-delta.md` criada e com status "Aceito"
- `docs/adr/ADR-0002-ingestao-incremental.md` criada e com status "Aceito"
- `docs/adr/ADR-0003-registro-tabelas.md` criada e com status "Aceito"
- `docs/adr/ADR-0004-orquestracao.md` criada e com status "Aceito"
- `docs/adr/ADR-0005-validacao-qualidade.md` criada e com status "Aceito"
- Nenhum notebook de pipeline criado ainda

---

## Sessao 2 — Setup do ambiente (1h)

**Pre-requisito:** ADR-0001 e ADR-0003 com status "Aceito".

**Objetivo:** Validar que o ambiente Databricks Community Edition e operacional antes de qualquer notebook de producao.

### Tarefas
1. Criar conta Databricks Community Edition (`community.cloud.databricks.com`)
2. Criar cluster single-node (Runtime 14.x LTS ou superior)
3. Conectar repositorio GitHub ao Databricks Repos
4. Criar estrutura de caminhos DBFS conforme ADR-0001: `/delta/bronze/`, `/delta/silver/`, `/delta/gold/`
5. Verificar conectividade com a API BCB: chamada HTTP de teste num notebook scratch para `https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados`
6. Registrar no Hive Metastore os schemas que serao usados (conforme ADR-0003), mesmo que as tabelas ainda nao existam

### Criterio de conclusao ("done")
- Cluster em estado Running
- Repositorio GitHub sincronizado no Databricks Repos
- Chamada de teste para a API BCB retorna JSON com sucesso a partir de um notebook
- Caminhos DBFS decididos em ADR-0001 estao documentados como variaveis de configuracao no topo de um arquivo de configuracao compartilhado (nao inline em cada notebook)

**Checkpoint de validacao:**
```python
import requests
r = requests.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados?formato=json&dataInicial=01/01/2026&dataFinal=31/01/2026")
assert r.status_code == 200, f"API BCB indisponivel: {r.status_code}"
assert len(r.json()) > 0, "Resposta vazia da API BCB"
```

---

## Sessao 3 — Notebook Bronze (2h)

**Pre-requisito:** Fases 0, 1 e 2 concluidas. ADR-0001, ADR-0002 e ADR-0003 com status "Aceito".

**Objetivo:** Ingestao das 3 series da API BCB para Delta Lake na camada bronze, sem transformacao, com suporte a execucao incremental conforme ADR-0002.

### Tarefas
1. Implementar chamada HTTP para as 3 series (USD/BRL cod. 1, Selic cod. 11, IPCA cod. 433) com janela de datas parametrizavel via widgets Databricks
2. Gravar resposta JSON bruta como Delta Table no caminho definido em ADR-0001 (`/delta/bronze/bcb/{serie_id}/`)
3. Adicionar colunas de metadados: `ingest_ts` (timestamp de execucao), `serie_id`, `source_url`
4. Implementar MERGE INTO na bronze para idempotencia conforme ADR-0002: chave `(serie_id, data)`
5. Registrar a tabela no Hive Metastore conforme ADR-0003
6. Cabecalho de celula explicando o que o notebook faz e referenciando as ADRs que o governam

### Criterio de conclusao ("done")
- Notebook executa sem erros do inicio ao fim
- `spark.read.format("delta").load("/delta/bronze/bcb/1/")` retorna registros das 3 series
- Executar o notebook duas vezes com a mesma janela de datas nao duplica registros (MERGE funciona)
- `DESCRIBE HISTORY` mostra pelo menos 2 versoes (primeira carga + merge subsequente)
- Tabela registrada no Hive Metastore: `SELECT COUNT(*) FROM bronze_bcb` funciona sem path absoluto

**Checkpoint de validacao:**
```sql
SELECT serie_id, COUNT(*) AS registros, MIN(data) AS primeiro, MAX(data) AS ultimo
FROM bronze_bcb
GROUP BY serie_id
```
Deve retornar 1 linha por serie com contagem coerente com a janela de datas solicitada.

---

## Sessao 4 — Notebook Silver (2.5h)

**Pre-requisito:** Fase 3 concluida. ADR-0001, ADR-0002 e ADR-0003 com status "Aceito".

**Objetivo:** Transformacao da bronze para silver com limpeza, tipagem, deduplicacao e particionamento por data.

### Tarefas
1. Ler da camada bronze via nome logico de tabela (Hive Metastore, conforme ADR-0003)
2. Aplicar transformacoes:
   - Cast de `data` de string para `DateType`
   - Cast de `valor` para `DoubleType`
   - Remover registros com `valor IS NULL` (IPCA tem gaps historicos)
   - Adicionar colunas `ano` e `mes` derivadas de `data` (para particionamento)
3. Implementar MERGE INTO na silver usando `(serie_id, data)` como chave de upsert (conforme ADR-0002)
4. Gravar particionado por `ano` e `mes`: `/delta/silver/bcb/` (conforme ADR-0001)
5. Adicionar Delta constraint: `ALTER TABLE silver_bcb ADD CONSTRAINT valor_positivo CHECK (valor > 0)` para series de preco
6. Registrar a tabela no Hive Metastore (conforme ADR-0003)

### Criterio de conclusao ("done")
- Notebook executa sem erros
- `valor` e do tipo `double`, `data` e do tipo `date` em todas as series
- MERGE INTO funciona: re-executar o notebook com a mesma janela nao altera a contagem de registros
- Constraint de valor positivo ativa e visivel em `SHOW TBLPROPERTIES`
- `DESCRIBE DETAIL silver_bcb` mostra `numFiles` e `sizeInBytes` coerentes

**Checkpoint de validacao:**
```sql
SELECT serie_id,
       typeof(valor) AS tipo_valor,
       typeof(data)  AS tipo_data,
       COUNT(*)      AS total,
       COUNT(DISTINCT data) AS datas_unicas
FROM silver_bcb
GROUP BY serie_id, typeof(valor), typeof(data)
```
Deve mostrar `double` e `date` sem valores nulos.

---

## Sessao 5 — Notebook Gold (2.5h)

**Pre-requisito:** Fase 4 concluida.

**Objetivo:** Construir o modelo analitico `fct_indicadores` e `dim_data`, consultavel via SQL, com OPTIMIZE e time travel demonstrado.

### Tarefas
1. Criar `dim_data` com calendario completo cobrindo o range dos dados silver (colunas: `data_id`, `data`, `ano`, `mes`, `trimestre`, `dia_semana`, `is_dia_util`)
2. Criar `fct_indicadores` pivotando as 3 series em colunas: `data`, `usd_brl`, `selic_aa`, `ipca_mensal`
   - Series diarias (USD/BRL, Selic): valor do dia
   - IPCA mensal: forward fill para todos os dias do mes
3. Aplicar `OPTIMIZE` na tabela gold para compactar small files
4. Aplicar `ZORDER BY data` para otimizar queries com filtro temporal
5. Demonstrar time travel: `SELECT * FROM fct_indicadores VERSION AS OF 0`
6. Registrar as tabelas no Hive Metastore (conforme ADR-0003)

### Criterio de conclusao ("done")
- `fct_indicadores` tem 1 linha por dia de calendario, sem gaps nas datas com dados disponiveis
- `dim_data` cobre todo o range presente em `fct_indicadores`
- Query SQL direto na gold funciona: `SELECT * FROM fct_indicadores WHERE ano = 2026 LIMIT 10`
- `DESCRIBE HISTORY fct_indicadores` mostra operacao OPTIMIZE registrada
- Time travel funciona: consulta com `VERSION AS OF 0` retorna dados

**Checkpoint de validacao:**
```sql
SELECT
  COUNT(*)            AS total_dias,
  COUNT(usd_brl)      AS dias_com_cambio,
  COUNT(selic_aa)     AS dias_com_selic,
  COUNT(ipca_mensal)  AS dias_com_ipca,
  MIN(data)           AS primeiro_dia,
  MAX(data)           AS ultimo_dia
FROM fct_indicadores
```
`total_dias` deve ser igual a `dias_com_cambio` e `dias_com_selic`.

---

## Sessao 6 — Notebook Quality Checks (2h)

**Pre-requisito:** Fase 5 concluida. ADR-0005 com status "Aceito".

**Objetivo:** Validacoes explícitas do pipeline com assertions Python e constraints Delta, conforme ADR-0005.

### Tarefas
1. Validacoes na bronze:
   - Contagem de registros por serie vs. janela de datas esperada (tolerancia para feriados)
   - Ausencia de `ingest_ts` nulo
2. Validacoes na silver:
   - Zero registros com `valor IS NULL`
   - Sem duplicatas por `(serie_id, data)`
   - Range de valores plausivel: Selic entre 0.01 e 50.0, IPCA entre -5.0 e 30.0, USD/BRL entre 1.0 e 20.0
3. Validacoes na gold:
   - `fct_indicadores` nao tem lacunas de datas em dias uteis (join com `dim_data`)
   - `dim_data` cobre 100% das datas presentes em `fct_indicadores`
4. Cada validacao lanca excecao com mensagem descritiva se falhar: o que falhou, valor encontrado vs. esperado
5. Celula final com sumario: quantas verificacoes passaram / falharam

### Criterio de conclusao ("done")
- Notebook executa sem erros sobre os dados correntes
- Pelo menos 10 assertions implementadas cobrindo as 3 camadas
- Cada assertion tem mensagem de erro descritiva
- Celula de sumario imprime `"Todas as X verificacoes passaram"` ao final

---

## Sessao 7 — Databricks Workflow (2h)

**Pre-requisito:** Fases 3, 4, 5 e 6 concluidas. ADR-0004 com status "Aceito".

**Objetivo:** Montar o job Databricks com as 4 tasks encadeadas e exportar a definicao JSON, conforme ADR-0004.

### Tarefas
1. Criar o Workflow via UI do Databricks com as tasks em sequencia:
   ```
   bronze_ingest -> silver_transform -> gold_model -> quality_checks
   ```
2. Configurar cada task para usar o notebook correspondente no Repos
3. Configurar parametros: widgets de data (`data_inicio`, `data_fim`) passados como job parameters
4. Definir dependencia explicita entre tasks (`depends_on`)
5. Executar o workflow completo uma vez e verificar que todas as tasks passam
6. Exportar a definicao do workflow como JSON para `workflows/bcb_pipeline.json`
7. Executar o workflow uma segunda vez com a mesma janela para validar idempotencia

### Criterio de conclusao ("done")
- Workflow executa de ponta a ponta com status "Succeeded" na UI
- Cada task mostra duracao e status individualmente na UI
- `workflows/bcb_pipeline.json` esta no repositorio com a definicao completa
- Segunda execucao com mesma janela: `SELECT COUNT(*) FROM fct_indicadores` retorna valor identico

**Checkpoint de validacao:**
Registrar a contagem antes e depois da segunda execucao do workflow. Os valores devem ser identicos.

---

## Sessao 8 — Documentacao e revisao final (1h)

**Pre-requisito:** Fases 6 e 7 concluidas.

**Objetivo:** README publicavel, `architecture.md` com comparacao fundamentada AWS vs Databricks, e revisao final do repositorio como portfolio.

### Tarefas — README.md
1. Descricao do projeto em 3-4 linhas
2. Diagrama textual da arquitetura medallion (Bronze -> Silver -> Gold)
3. Tabela de comparacao AWS vs Databricks (conforme documento de concepcao)
4. Instrucoes de reproducao: como importar notebooks, criar cluster, executar o workflow
5. Secao "O que este projeto demonstra" — lista dos conceitos Databricks cobertos

### Tarefas — docs/architecture.md
1. Diagrama de fluxo: API BCB -> Bronze Delta -> Silver Delta -> Gold Delta -> SQL
2. Decisoes de design com referencia as ADRs aceitas:
   - Por que MERGE INTO (ADR-0002)
   - Por que DBFS e nao Unity Catalog (ADR-0001)
   - Como o Workflow substitui o Airflow (ADR-0004)
3. Comparacao detalhada com o `bcb-pipeline` (Projeto 1): mesma fonte, decisoes diferentes
4. Limitacoes do Community Edition relevantes para este projeto

### Tarefas — revisao final
1. Executar o workflow completo uma ultima vez — confirmar que passa sem intervencao
2. Revisar todos os notebooks: remover celulas de debug, confirmar valores default nos widgets
3. Confirmar que cada notebook tem celula de cabecalho explicando o que faz e referenciando ADRs
4. Verificar que nenhuma credencial, token ou dado sensivel esta no repositorio

### Criterio de conclusao ("done") — projeto completo
- Uma pessoa externa consegue clonar o repo, importar os notebooks, criar o cluster e executar o workflow seguindo apenas o README
- Todos os 4 notebooks executam sem erros em sequencia manual
- `workflows/bcb_pipeline.json` esta presente e documentado
- `docs/architecture.md` tem a comparacao AWS vs Databricks preenchida com referencia as ADRs
- Todos os ADRs (ADR-0000 a ADR-0005) estao em `docs/adr/` com status "Aceito"
- Nenhuma referencia a "TODO" ou placeholder nos arquivos de documentacao

---

## Checkpoints de validacao por fase

| Fase | Checkpoint | Evidencia esperada |
|------|------------|--------------------|
| 0 | ADR-0000 criada e aceita | Arquivo `docs/adr/ADR-0000-convencoes-adr.md` com status "Aceito" |
| 1 | ADR-0001 a ADR-0005 aceitas | 5 arquivos em `docs/adr/` com status "Aceito" |
| 2 | API BCB acessivel do cluster | Assert Python passa sem erro |
| 3 | Bronze idempotente | Segunda execucao: COUNT identico |
| 4 | Silver sem duplicatas | Query de deduplicacao retorna zero |
| 5 | Gold consultavel via SQL | Query com filtro de ano retorna dados |
| 6 | 10+ assertions passando | Celula de sumario imprime sucesso |
| 7 | Workflow idempotente | COUNT antes = COUNT depois da segunda execucao |
| 8 | Repositorio publicavel | README sem TODO, ADRs completas |

---

## Riscos e mitigacoes

| Risco | Probabilidade | Mitigacao |
|-------|--------------|-----------|
| Cluster Community Edition para por inatividade durante sessao longa | Alta | Salvar notebooks frequentemente; o estado Delta persiste no DBFS apos reinicio do cluster |
| API BCB indisponivel ou com rate limiting | Baixa | Implementar retry simples (3 tentativas com sleep exponencial) no notebook Bronze |
| MERGE INTO lento para backfill de historico longo | Media | Conforme ADR-0002: usar INSERT OVERWRITE no backfill inicial; MERGE apenas nas execucoes incrementais subsequentes |
| Exportacao do Workflow JSON nao captura todos os parametros | Media | Validar o JSON re-importando num segundo workspace antes de encerrar a Fase 7 |
| Schema evolution quebra notebooks downstream | Baixa | Delta Lake rejeita por padrao mudancas de schema incompativeis (schema enforcement ativo) |
| ADR contradita por limitacao tecnica descoberta na implementacao | Media | Abrir revisao da ADR afetada antes de contornar a decisao; nao implementar workarounds silenciosos |

---

## Proximos passos imediatos

1. Criar `docs/adr/ADR-0000-convencoes-adr.md` — este e o unico entregavel que desbloqueia todo o restante
2. Apos ADR-0000 aceita, redigir ADR-0001 a ADR-0005 na Sessao 1
3. So entao iniciar o Setup do ambiente (Sessao 2)
