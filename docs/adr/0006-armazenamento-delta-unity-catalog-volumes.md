# ADR-0006: Armazenamento Delta — Unity Catalog Volumes como storage das camadas medallion

## Status
Aceito

## Contexto

A ADR-0001 decidiu usar DBFS com caminhos absolutos (`/delta/bronze/bcb/`, `/delta/silver/bcb/`, `/delta/gold/`) porque a plataforma do projeto era o Databricks Community Edition, que não suporta Unity Catalog. Essa limitação foi documentada explicitamente na ADR-0001 como um trade-off de plataforma.

A plataforma mudou. O projeto passou a rodar no **Azure Databricks Trial**, que habilita Unity Catalog por padrão e desabilita o acesso ao DBFS root por política de segurança. Ao tentar executar `dbutils.fs.mkdirs("/delta/bronze/bcb/")`, o runtime retornou:

```
ExecutionError: [DBFS_DISABLED] Public DBFS root is disabled. Access is denied on path: /delta/bronze/bcb
```

O DBFS root está desabilitado no Azure Databricks Trial porque o Unity Catalog o substitui como modelo padrão de armazenamento e governança. Continuar com caminhos DBFS não é viável nessa plataforma.

O Unity Catalog organiza o armazenamento em uma hierarquia de três níveis: `catalog > schema > volume`. **Volumes** são objetos de armazenamento de arquivos dentro dessa hierarquia, acessíveis por caminhos do tipo `/Volumes/<catalog>/<schema>/<volume>/`. Eles oferecem as mesmas garantias de governança (controle de acesso, auditoria, linhagem) que as tabelas gerenciadas do Unity Catalog.

Esta mudança representa uma melhoria de plataforma em relação à restrição original: o Unity Catalog é o modelo moderno e recomendado pela Databricks para todos os ambientes de produção, e sua adoção agrega valor ao portfólio ao demonstrar familiaridade com o stack atual da plataforma.

## Decisão

Utilizar **Unity Catalog Volumes** para armazenamento dos arquivos Delta das camadas bronze, silver e gold, com caminhos organizados sob o catálogo `main` e o schema `default`, que são os recursos criados automaticamente no Azure Databricks Trial.

A estrutura de caminhos por camada é:

| Camada | Caminho no Volume | Conteúdo |
|--------|-------------------|----------|
| Bronze | `/Volumes/main/default/bronze/bcb/{serie_id}/` | JSON bruto da API BCB, sem transformação |
| Silver | `/Volumes/main/default/silver/bcb/` | Dados limpos, tipados, particionados por `ano` e `mes` |
| Gold   | `/Volumes/main/default/gold/` | Modelo analítico (`fct_indicadores`, `dim_data`) |

O Volume para cada camada será um Volume externo ou gerenciado criado dentro do schema `default` do catálogo `main`. Os caminhos absolutos continuam sendo definidos como variáveis de configuração em arquivo compartilhado — nenhum notebook os referencia como literais inline.

As tabelas Delta registradas no Unity Catalog (decisão complementar da ADR-0003) continuam seguindo a hierarquia `main.default.<nome_tabela>`, consistente com o catálogo e schema escolhidos aqui.

## Consequências

### Positivas
- Compatível com Azure Databricks Trial — elimina o erro `DBFS_DISABLED` que bloqueava a execução
- Unity Catalog é o modelo de governança moderno da Databricks, adotado por padrão em todos os ambientes gerenciados (Standard, Premium, Enterprise, Trial)
- Volumes herdam controle de acesso baseado em roles do Unity Catalog — segregação por usuário/grupo sem configuração adicional
- Auditoria de acesso a arquivos integrada ao Unity Catalog audit log
- Linhagem de dados automática entre volumes e tabelas Delta registradas no mesmo catálogo
- Caminhos `/Volumes/` são portáveis entre workspaces do mesmo Azure Databricks Account, diferente dos caminhos DBFS que eram workspace-específicos
- Narrativa de portfólio mais forte: demonstra uso do stack atual de produção Databricks, não um workaround de edição gratuita

### Negativas / Trade-offs
- Os notebooks e o arquivo de configuração de caminhos precisam ser atualizados de `/delta/` para `/Volumes/main/default/`
- O Volume precisa ser criado no Unity Catalog antes da primeira execução dos notebooks (operação de infraestrutura, não de código de pipeline)
- O catálogo `main` e o schema `default` são recursos padrão do Trial; em um ambiente corporativo, o catalog e schema seriam definidos por política de governança da organização, o que exigiria atualizar os caminhos novamente
- ADR-0003 precisa ser revisada para confirmar que o registro de tabelas no Unity Catalog (`main.default.<tabela>`) está alinhado com os Volumes escolhidos aqui

## Alternativas consideradas

- **Manter DBFS com configuração explícita para habilitar o DBFS root**: o Azure Databricks permite reabilitar o DBFS root por configuração de workspace. Rejeitado porque vai contra a direção da plataforma (Databricks está depreciando o DBFS root progressivamente), não seria disponível em workspaces corporativos e desperdiça a oportunidade de demonstrar Unity Catalog no portfólio.

- **S3 externo montado via `dbutils.fs.mount()`**: montar um bucket S3 da AWS no workspace Azure Databricks. Rejeitado porque adiciona dependência de credenciais AWS em ambiente Azure, aumenta a complexidade operacional do projeto de portfólio e mistura dois provedores de nuvem sem justificativa técnica.

- **ADLS Gen2 externo como storage Delta sem Unity Catalog**: usar Azure Data Lake Storage diretamente com credenciais de service principal. Rejeitado porque replica a complexidade do S3 externo, não usa o Unity Catalog disponível na plataforma e é mais difícil de reproduzir por avaliadores do portfólio.

## Relação com outras ADRs

- **ADR-0001**: esta ADR substitui a ADR-0001. A decisão original de usar DBFS foi motivada por limitação de plataforma (Community Edition sem Unity Catalog) que não se aplica mais. O raciocínio da ADR-0001 permanece válido como contexto histórico.
- **ADR-0003** (Registro de tabelas no Hive Metastore vs. caminhos absolutos): precisa ser revisada para confirmar alinhamento com Unity Catalog. O registro de tabelas em `main.default.<tabela>` é consistente com os Volumes em `main/default/`, mas a ADR-0003 faz referência ao Hive Metastore legado, que é substituído pelo Unity Catalog nesta plataforma.

## Revisão
Elaborado por: Claude (Agente IA) — arquiteto-dados
Data/hora: 2026-07-22 03:19 BRT

## Aprovação
Aprovado por: Lucas de Araújo
Data/hora: 2026-07-22 03:28 BRT
