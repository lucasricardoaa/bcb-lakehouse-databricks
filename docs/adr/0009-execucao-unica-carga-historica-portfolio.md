# ADR-0009: Execução única com carga histórica para portfólio estático

## Status
Aceito

## Contexto

O projeto bcb-lakehouse-databricks é executado em um workspace Azure Databricks Trial, que possui custo contínuo enquanto ativo e será encerrado após a execução do pipeline. Manter a infraestrutura ativa para execuções recorrentes geraria custo sem nenhum benefício, dado que o objetivo do projeto é exclusivamente compor um portfólio de engenharia de dados permanentemente preservado no GitHub.

A ADR-0002 projetou o pipeline para ingestão incremental recorrente com janela padrão de 30 dias, utilizando MERGE INTO como mecanismo de upsert. Essa decisão foi correta no contexto de um pipeline em produção, mas o objetivo do projeto mudou: ele é um **projeto de portfólio estático**, executado uma única vez.

Dado o encerramento planejado do workspace, a janela de execução deve ser definida de forma a maximizar o valor do dataset produzido. Uma janela histórica ampla (01/01/2020 a 22/07/2026) captura aproximadamente 6 anos de dados reais das 3 séries BCB:

| Série | Código BCB | Volume estimado na janela |
|-------|-----------|--------------------------|
| Câmbio USD/BRL | 1 | ~1.700 registros (dias úteis) |
| Taxa Selic | 11 | ~1.700 registros (dias úteis) |
| IPCA | 433 | ~78 registros (mensais) |

Esse volume é suficiente para que os quality checks da camada Gold operem sobre dados reais com variações estatísticas significativas (período inclui pandemia, ciclos de alta e baixa da Selic, inflação elevada e normalização), tornando o resultado do portfólio substancialmente mais relevante do que uma janela de 30 dias.

## Decisão

Executar o pipeline **uma única vez** com os parâmetros fixos abaixo, passados manualmente ao Databricks Workflow no momento da execução:

```
data_inicio = 01/01/2020
data_fim    = 22/07/2026
```

Após a execução bem-sucedida e validação dos quality checks, o workspace Azure Databricks Trial será encerrado. O projeto ficará preservado exclusivamente no repositório GitHub com os artefatos de código, notebooks, definição do Workflow e esta documentação.

Não há alteração nos mecanismos internos do pipeline: o MERGE INTO definido na ADR-0002 permanece como estratégia de ingestão. A mudança é estritamente no modo de uso — de recorrente para pontual — e na definição explícita da janela histórica.

## Consequências

### Positivas
- Dataset de ~6 anos de dados reais do BCB, com variações econômicas relevantes, torna o portfólio mais convincente para recrutadores e revisores técnicos
- Quality checks da camada Gold operam sobre dados com variância real (não apenas os últimos 30 dias), aumentando a credibilidade dos testes de qualidade documentados
- Encerramento planejado do workspace elimina custo contínuo de infraestrutura após a execução
- A decisão é documentada explicitamente, deixando claro que a ausência de execuções recorrentes é uma escolha consciente de escopo, não uma limitação técnica
- O mecanismo MERGE INTO, mesmo utilizado uma única vez, demonstra a implementação correta de idempotência — propriedade relevante para o portfólio

### Negativas / Trade-offs
- A janela histórica ampla aumenta o volume de chamadas à API pública do BCB; o notebook de ingestão deve respeitar possíveis limites de rate da API durante a execução
- Após o encerramento do workspace, não será possível reexecutar o pipeline sem provisionar um novo ambiente Databricks — o resultado da execução única é definitivo
- O Workflow definido na ADR-0004 foi concebido com valores default de 30 dias e foco em execução recorrente; será usado para uma única execução manual com parâmetros sobrescritos, o que é funcionalmente correto mas representa um uso diferente do planejado originalmente

## Alternativas consideradas

- **Manter a janela padrão de 30 dias (ADR-0002)**: executar uma única vez com os últimos 30 dias. Rejeitado porque produz um dataset pequeno, sem variações econômicas relevantes e pouco representativo para um portfólio — derrota o objetivo de demonstrar o pipeline com dados reais significativos.

- **Janela desde a origem histórica de cada série (ex: desde 1984 para câmbio)**: capturar todo o histórico disponível na API BCB. Rejeitado porque o volume de dados para décadas de histórico não agrega valor proporcional ao risco de timeout ou rate limiting durante a ingestão em um ambiente Trial com recursos limitados; a janela de 2020 a 2026 já cobre os eventos econômicos mais relevantes.

- **Manter infraestrutura ativa para execuções periódicas futuras**: continuar executando o pipeline mensalmente para manter o dataset atualizado. Rejeitado porque o custo contínuo do Azure Databricks Trial não é sustentável para um projeto de portfólio sem receita associada, e o objetivo de demonstração está cumprido após a execução única.

## Relação com outras ADRs

- **ADR-0002 (MERGE INTO vs INSERT OVERWRITE)**: esta ADR não contradiz nem substitui a ADR-0002. O mecanismo MERGE INTO permanece como estratégia de ingestão; o que muda é que o pipeline será executado uma única vez em vez de de forma recorrente. A propriedade de idempotência garantida pelo MERGE INTO continua válida e demonstrável — se a execução for interrompida e reiniciada (ex: cluster auto-terminate após 60 min de inatividade), o resultado será idêntico.

- **ADR-0004 (Databricks Workflows)**: o Workflow projetado na ADR-0004 foi concebido para execução recorrente com valores default de 30 dias. Esta ADR define que ele será usado para uma única execução manual com os parâmetros `data_inicio = 01/01/2020` e `data_fim = 22/07/2026` sobrescritos manualmente na UI. A estrutura do Workflow (4 tasks encadeadas, passagem de parâmetros via widgets) permanece inalterada.

## Revisão
Elaborado por: Claude (Agente IA) — arquiteto-dados
Data/hora: 2026-07-22 18:35 BRT

## Aprovação
Aprovado por: Lucas de Araújo
Data/hora: 2026-07-22 BRT
