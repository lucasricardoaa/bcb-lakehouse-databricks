# ADR-0005: Validação de qualidade — assertions Python vs framework externo

## Status
Aceito

## Contexto

O pipeline precisa de um mecanismo de validação de qualidade que verifique a integridade dos dados em cada camada (Bronze, Silver, Gold) antes de declarar uma execução como bem-sucedida. Falhas de qualidade devem interromper o Workflow (ADR-0004) e produzir mensagens de erro descritivas que identifiquem exatamente o que falhou.

Dois modelos foram avaliados:

**Modelo A — Assertions Python nativas:** funções Python que executam queries Spark/SQL, comparam o resultado com o valor esperado, e lançam exceções com mensagens descritivas em caso de falha. Sem dependências externas além do PySpark.

**Modelo B — Framework externo de qualidade de dados:** ferramentas especializadas como Great Expectations, Soda Core ou dbt test que oferecem catálogos de validações pré-construídas, relatórios HTML/JSON e integração com catálogos de dados.

O contexto relevante para esta decisão:

1. **Plataforma**: Azure Databricks Trial. Frameworks externos podem ser instalados via `pip install` em células de notebook ou como cluster-scoped libraries (que persistem entre reinicializações). A simplicidade das assertions Python foi preferida independentemente dessa disponibilidade.

2. **Projeto anterior (`bcb-pipeline`)**: usa Great Expectations para validação de qualidade, gerando Data Docs HTML como evidência auditável. A comparação entre as duas abordagens é relevante para o portfólio.

3. **Escopo das validações**: as verificações necessárias são bem definidas — contagem por série, ausência de nulos, ranges plausíveis de valor, ausência de duplicatas e cobertura de datas. Não há necessidade de um catálogo extenso de expectativas.

4. **Integração com Delta**: o Delta Lake oferece `ADD CONSTRAINT` para validações no nível de storage — complemento natural às assertions Python.

## Decisão

Adotar **assertions Python nativas** como estratégia de validação de qualidade, implementadas no notebook `04_quality_checks.py`.

**Estrutura de cada assertion:**

```python
def assert_sem_nulos(df, coluna, contexto):
    contagem = df.filter(df[coluna].isNull()).count()
    assert contagem == 0, (
        f"[FALHA] {contexto}: coluna '{coluna}' tem {contagem} valores nulos. "
        f"Esperado: 0."
    )
```

**Padrão obrigatório para mensagens de erro:**
```
[FALHA] {contexto}: {o que foi verificado}. Encontrado: {valor_real}. Esperado: {valor_esperado}.
```

**14 assertions implementadas:**

| Camada | Assert | Validação |
|--------|--------|-----------|
| Bronze | 1 | Ausência de `ingest_ts` nulo |
| Bronze | 2 | Ausência de `serie_id` nulo |
| Bronze | 3 | Presença das 3 séries (1, 11, 433) |
| Silver | 4 | Zero registros com `valor IS NULL` |
| Silver | 5 | Ausência de duplicatas por `(serie_id, data)` |
| Silver | 6 | Range plausível: Selic entre 0,001 e 50,0 (taxa diária; mínimo histórico ~0,00787% no período COVID) |
| Silver | 7 | Range plausível: IPCA entre -5,0 e 30,0 |
| Silver | 8 | Range plausível: USD/BRL entre 1,0 e 20,0 |
| Silver | 9 | Tipos corretos: `valor` como `double`, `data` como `date` |
| Gold | 10 | `fct_indicadores` tem registros |
| Gold | 11 | `fct_indicadores` sem datas nulas |
| Gold | 12 | `dim_data` cobre 100% das datas de `fct_indicadores` |
| Gold | 13 | `dim_data` sem duplicatas por `data` |
| Gold | 14 | `fct_indicadores` sem duplicatas por `data` |

**Célula de sumário obrigatória:** o notebook deve encerrar com uma célula que imprime o total de verificações executadas e confirma `"Todas as X verificações passaram"` ou lista as falhas.

**Integração com Workflow:** assertions que lançam exceção não capturada interrompem a task `quality_checks` no Workflow (ADR-0004), marcando o job como falho e impedindo entregas subsequentes.

**Comparação com o `bcb-pipeline`:**

| Critério | bcb-pipeline (Great Expectations) | bcb-lakehouse-databricks (assertions Python) |
|----------|---------------------------------|---------------------------------------------|
| Dependência | `great_expectations` (pacote externo) | Nenhuma além do PySpark |
| Persistência no cluster | Não persiste entre reinicializações | N/A — código Python puro |
| Relatório de qualidade | Data Docs HTML navegável | Saída de texto no notebook |
| Catálogo de expectativas | +50 tipos pré-construídos | Assertions customizadas |
| Curva de aprendizado | Alta (expectation suites, checkpoints) | Baixa (Python padrão) |
| Integração com Delta constraints | Indireta | Nativa (via SQL no notebook) |
| Evidência auditável | HTML persistido no S3 | Log de execução do Workflow |

## Consequências

### Positivas
- **Zero dependências externas**: assertions Python puro não têm risco de falha por pacote não instalado ou versão incompatível — uma das vantagens para um projeto de portfólio onde o ambiente pode variar
- **Mensagens de erro descritivas e customizadas**: cada assertion pode incluir contexto específico do domínio (nome da série, janela de datas, valor encontrado vs. esperado), impossível com frameworks genéricos
- **Código Python legível e auditável**: qualquer engenheiro de dados entende as validações sem conhecer a API de nenhum framework
- **Integração natural com o Workflow**: exceções Python interrompem a task de qualidade e marcam o job como falho automaticamente, sem configuração adicional
- **Validação centralizada no notebook**: todas as regras de qualidade vivem em um único artefato versionado (`04_quality_checks.py`), facilitando auditoria e manutenção

### Negativas / Trade-offs
- **Sem relatório HTML de qualidade**: ao contrário do Great Expectations no `bcb-pipeline`, não há um artefato visual navegável das validações — a evidência é o log de execução do Workflow
- **Sem catálogo de expectativas reutilizável**: cada validação é implementada como função Python ad hoc; em projetos maiores, isso pode gerar duplicação sem um framework que centralize o catálogo
- **Manutenção manual de ranges**: os limites plausíveis de valor (Selic, IPCA, câmbio) são hardcoded nas assertions; mudanças de regime econômico podem exigir atualização manual dos parâmetros
- **Cobertura limitada de edge cases**: frameworks como Great Expectations têm expectativas para distribuições estatísticas, freshness de dados e correlações — validações que exigiriam implementação manual aqui

## Alternativas consideradas

- **Great Expectations**: framework de referência para qualidade de dados em Python, usado no `bcb-pipeline`. Oferece expectation suites, checkpoints e Data Docs HTML. Rejeitado porque adiciona overhead de configuração (expectation suites, checkpoints, Data Docs) desproporcional ao escopo das validações necessárias neste projeto; e porque as expectation suites e Data Docs não agregam valor de portfólio incremental — o `bcb-pipeline` já cobre essa demonstração.

- **Soda Core**: alternativa mais leve ao Great Expectations, com configuração em YAML. Rejeitado por adicionar uma camada de configuração YAML que obscurece as validações sem ganho de expressividade para o escopo deste projeto.

- **dbt tests**: usar dbt Core para definir testes de qualidade sobre as tabelas Delta registradas no Unity Catalog. Rejeitado porque requer um projeto dbt separado com configuração de conexão ao Databricks, adicionando infraestrutura além do escopo deste projeto de portfólio.

## Revisão
Elaborado por: Claude (Agente IA) — arquiteto-dados-aws
Data/hora: 2026-07-22 00:20 BRT

## Aprovação
Aprovado por: Lucas de Araújo
Data/hora: 2026-07-22 00:53 BRT
