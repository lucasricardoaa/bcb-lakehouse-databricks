# ADR-0002: Ingestão incremental — MERGE INTO vs INSERT OVERWRITE

## Status
Aceito

## Contexto

O pipeline ingere dados de 3 séries históricas da API pública do Banco Central do Brasil:

| Série | Código BCB | Frequência | Volume histórico |
|-------|-----------|------------|-----------------|
| Câmbio USD/BRL | 1 | Diária (dias úteis) | ~14.000 registros desde 1984 |
| Taxa Selic | 11 | Diária (dias úteis) | ~8.000 registros desde 1986 |
| IPCA | 433 | Mensal | ~360 registros desde 1980 |

O pipeline deve ser executável múltiplas vezes com a mesma janela de datas sem duplicar registros — requisito de **idempotência**. Essa é uma propriedade essencial para pipelines em produção e para o cenário deste projeto, onde o cluster Databricks Community Edition pode reiniciar e forçar reexecução.

Duas estratégias são viáveis para ingestão sobre Delta Lake:

- **`MERGE INTO`**: operação de upsert que compara registros pela chave definida. Se o registro já existe, atualiza; se não existe, insere. Garante idempotência por construção, ao custo de scan da tabela destino para comparação.
- **`INSERT OVERWRITE`**: substitui uma partição inteira (ou a tabela toda) pelos dados novos. Idempotente para partições completas, mas ineficiente para atualizações pontuais e arriscado se a partição de destino contiver dados que não estão no conjunto de entrada.

O projeto anterior (`bcb-pipeline` com Airflow + S3 + Athena) implementa ingestão incremental com particionamento Hive-style, onde cada execução sobrescreve a partição do dia/mês correspondente. Esse modelo é equivalente ao `INSERT OVERWRITE` por partição.

## Decisão

Adotar **`MERGE INTO` como estratégia padrão para execuções incrementais**, com `INSERT OVERWRITE` reservado exclusivamente para o backfill inicial do histórico completo.

**Chave de upsert:** `(serie_id, data)` — combinação que identifica unicamente um registro em qualquer das três séries.

**Regras por cenário:**

| Cenário | Estratégia | Justificativa |
|---------|-----------|---------------|
| Backfill inicial (todo o histórico) | `INSERT OVERWRITE` | Tabela vazia ou truncada; não há risco de sobrescrever dados divergentes; performance superior para volumes grandes |
| Execução incremental diária (janela de N dias) | `MERGE INTO` | Garante idempotência; execuções repetidas com a mesma janela produzem resultado idêntico |
| Reprocessamento de janela histórica específica | `MERGE INTO` | Atualiza apenas os registros da janela sem afetar o restante |

**Parâmetros obrigatórios nos notebooks:** cada notebook que implementa ingestão deve expor widgets `data_inicio` e `data_fim` para controle da janela. Valores default: últimos 30 dias a partir da data de execução.

**Estrutura do `MERGE INTO` na camada Bronze:**

```sql
MERGE INTO bronze_bcb AS destino
USING novos_registros AS origem
ON destino.serie_id = origem.serie_id AND destino.data = origem.data
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

## Consequências

### Positivas
- Idempotência garantida por construção: executar o pipeline duas vezes com a mesma janela produz exatamente o mesmo estado na tabela destino
- Compatível com o modelo de reexecução forçada pelo cluster Community Edition (que para após 2h de inatividade)
- `DESCRIBE HISTORY` registra cada operação de MERGE, permitindo auditoria do que foi inserido ou atualizado em cada execução
- A chave `(serie_id, data)` é semanticamente correta para os dados da API BCB — não há dois valores para a mesma série na mesma data
- Alinha com a funcionalidade Delta Lake que diferencia este projeto do `bcb-pipeline` (Parquet + Athena não suporta upsert nativo)

### Negativas / Trade-offs
- **Performance no backfill**: `MERGE INTO` sobre tabelas grandes realiza scan completo da tabela destino para encontrar registros correspondentes. Para o histórico completo (décadas de dados diários), `INSERT OVERWRITE` é significativamente mais rápido — por isso é a estratégia do backfill inicial
- **Complexidade de implementação**: notebooks precisam receber e processar parâmetros de janela de datas (widgets); a lógica de MERGE requer definição explícita de chave e cláusulas WHEN
- **Sem detecção de deleções**: o MERGE não remove da tabela destino registros que existiam antes mas não estão no conjunto de entrada — adequado para a API BCB (dados históricos não são deletados), mas deve ser documentado como limitação

## Alternativas consideradas

- **`INSERT OVERWRITE` para todas as execuções**: substituir sempre a partição completa do período da janela. Rejeitado para execuções incrementais porque a granularidade de partição (dia ou mês) pode não coincidir exatamente com a janela solicitada, gerando risco de apagar dados fora da janela mas dentro da mesma partição.

- **`INSERT INTO` sem MERGE**: inserir novos registros sem verificar duplicatas, confiar em deduplicação posterior. Rejeitado porque viola o requisito de idempotência — execuções repetidas acumulam duplicatas que precisam de tratamento adicional.

- **Deletar e reinserir por janela (`DELETE WHERE data BETWEEN ... THEN INSERT`)**: limpar o intervalo antes de inserir. Rejeitado porque gera duas operações Delta (duas entradas no `DESCRIBE HISTORY`) e não oferece vantagem sobre o `MERGE INTO` para este volume de dados.

## Revisão
Elaborado por: Claude (Agente IA) — arquiteto-dados-aws
Data/hora: 2026-07-22 00:20 BRT

## Aprovação
Aprovado por: Lucas de Araújo
Data/hora: 2026-07-22 00:53 BRT
