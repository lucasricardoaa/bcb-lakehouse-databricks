# ADR-0007: Registro de tabelas — Unity Catalog em substituição ao Hive Metastore legado

## Status
Aceito

## Contexto

A ADR-0003 decidiu registrar as tabelas Delta no **Hive Metastore local do workspace**, com nomes lógicos simples (`bronze_bcb`, `silver_bcb`, `fct_indicadores`, `dim_data`) e localização explícita no DBFS. Essa decisão foi correta no contexto do Databricks Community Edition, onde o Unity Catalog não estava disponível e o Hive Metastore era o único catálogo disponível.

A ADR-0006 registrou a mudança de plataforma para **Azure Databricks Trial**, que habilita o Unity Catalog por padrão e desabilita o DBFS root. Com essa mudança, o modelo de catálogo também muda: o Unity Catalog **substitui** o Hive Metastore legado como sistema de registro e governança de tabelas.

### Diferença entre Hive Metastore legado e Unity Catalog

O **Hive Metastore legado** é o catálogo padrão do Apache Spark, disponível em todas as edições do Databricks. Ele mantém um mapeamento plano entre nome de tabela e caminho físico no storage, sem hierarquia de catálogos, sem controle de acesso por objeto, sem auditoria centralizada e sem linhagem de dados. No Community Edition, é o único catálogo disponível.

O **Unity Catalog** é o plano de governança unificado da Databricks, com hierarquia de três níveis:

```
catalog  →  schema  →  tabela / volume
  main       default     bronze_bcb
```

Além da hierarquia, o Unity Catalog oferece: controle de acesso baseado em roles (RBAC) no nível de catálogo, schema, tabela e coluna; auditoria de queries e acessos integrada; linhagem automática entre tabelas e volumes; e isolamento de dados entre workspaces do mesmo Azure Databricks Account.

No Azure Databricks Trial, o catálogo `main` e o schema `default` são criados automaticamente na ativação do workspace. Esses são os recursos disponíveis sem configuração adicional de infraestrutura.

A ADR-0006 já definiu que os Volumes de storage ficam em `main/default/` (caminhos `/Volumes/main/default/bronze/`, `/Volumes/main/default/silver/`, `/Volumes/main/default/gold/`). O registro de tabelas no Unity Catalog deve ser consistente com esses recursos, usando o mesmo catálogo e schema.

## Decisão

Registrar todas as tabelas Delta no **Unity Catalog**, sob o catálogo `main` e o schema `default`, seguindo a convenção de nomes totalmente qualificados `main.default.<nome_tabela>`.

**Convenção de nomes lógicos:**

| Camada | Nome totalmente qualificado | Volume de storage (ADR-0006) |
|--------|----------------------------|------------------------------|
| Bronze | `main.default.bronze_bcb` | `/Volumes/main/default/bronze/bcb/` |
| Silver | `main.default.silver_bcb` | `/Volumes/main/default/silver/bcb/` |
| Gold — fato | `main.default.fct_indicadores` | `/Volumes/main/default/gold/fct_indicadores/` |
| Gold — dimensão | `main.default.dim_data` | `/Volumes/main/default/gold/dim_data/` |

**Tipo de tabela:** tabelas externas (`CREATE TABLE IF NOT EXISTS ... USING DELTA LOCATION '...'`), com localização explícita no Volume definido pela ADR-0006. O uso de tabelas externas preserva os dados no Volume caso a tabela seja removida do catálogo por acidente.

**Responsabilidade de registro:** cada notebook registra sua própria tabela de saída após a primeira escrita, usando `CREATE TABLE IF NOT EXISTS` para garantir idempotência. O nome totalmente qualificado (`main.default.<nome>`) é sempre usado — nunca o nome curto sem prefixo de catálogo e schema.

**Padrão de referência em queries:** todas as queries SQL nos notebooks usam o nome totalmente qualificado:

```sql
SELECT * FROM main.default.silver_bcb
DESCRIBE HISTORY main.default.fct_indicadores
MERGE INTO main.default.bronze_bcb AS destino ...
```

**Escopo dos registros da ADR-0003:** os nomes lógicos curtos definidos pela ADR-0003 (`bronze_bcb`, `silver_bcb`, etc.) são mantidos como sufixo — apenas o prefixo de catálogo e schema muda de implícito (Hive Metastore) para explícito (`main.default`).

## Consequências

### Positivas
- Alinhamento completo com a ADR-0006: catálogo `main`, schema `default` e Volumes em `main/default/` são o mesmo namespace — tabelas e arquivos Delta ficam no mesmo contexto hierárquico
- Unity Catalog oferece controle de acesso granular por tabela e coluna sem configuração adicional no Trial
- Linhagem automática entre os Volumes (storage) e as tabelas registradas no mesmo catálogo e schema
- Nomes totalmente qualificados eliminam ambiguidade de contexto: `main.default.silver_bcb` é inequívoco independentemente do catálogo ativo na sessão
- Narrativa de portfólio mais forte: Unity Catalog é o modelo de governança de produção atual da Databricks, e esta ADR documenta o raciocínio da adoção
- Compatível com ferramentas de BI e SQL que conectam via JDBC/ODBC ao Databricks — o nome totalmente qualificado é o identificador portável

### Negativas / Trade-offs
- Todos os notebooks e queries que referenciam tabelas pelo nome curto (padrão da ADR-0003) precisam ser atualizados para o nome totalmente qualificado `main.default.<nome>`
- O catálogo `main` e o schema `default` são padrões do Trial; em um ambiente corporativo, o catalog e schema seguiriam políticas de governança da organização, exigindo nova atualização de nomes
- `CREATE TABLE IF NOT EXISTS` no Unity Catalog requer que o usuário tenha privilégio `CREATE TABLE` no schema `default` — no Trial, o criador do workspace tem esse privilégio por padrão, mas deve ser documentado para reprodução
- Tabelas externas no Unity Catalog não são removidas quando o Volume é deletado, e vice-versa — a consistência entre storage e catálogo deve ser mantida manualmente durante operações de limpeza

## Alternativas consideradas

- **Manter o Hive Metastore legado com `USE CATALOG hive_metastore`**: no Azure Databricks com Unity Catalog habilitado, o Hive Metastore legado ainda está acessível via `USE CATALOG hive_metastore`. Rejeitado porque os dados estão nos Volumes do Unity Catalog (ADR-0006), e registrar tabelas no Hive Metastore legado apontando para Volumes do Unity Catalog mistura dois sistemas de governança sem benefício — e a Databricks está depreciando o acesso ao Hive Metastore legado progressivamente.

- **Tabelas gerenciadas pelo Unity Catalog (sem `LOCATION` explícita)**: deixar o Unity Catalog gerenciar o ciclo de vida do storage automaticamente, sem especificar o caminho do Volume. Rejeitado porque tabelas gerenciadas têm storage deletado junto com a tabela — para um projeto de portfólio onde o cluster pode ser recriado, o risco de perda de dados por `DROP TABLE` acidental é maior do que com tabelas externas que preservam os arquivos no Volume.

- **Referenciar tabelas sempre por caminho direto no Volume (`delta.\`/Volumes/main/default/silver/bcb/\``)**: evitar o registro no catálogo e usar apenas caminhos absolutos nas queries. Rejeitado pelos mesmos motivos da ADR-0003: queries verbosas, acoplamento ao caminho físico e perda de `DESCRIBE HISTORY` e `DESCRIBE DETAIL` por nome lógico.

## Relação com outras ADRs

- **ADR-0003**: esta ADR substitui a ADR-0003. A decisão original de registrar tabelas no Hive Metastore foi motivada pela ausência de Unity Catalog no Community Edition — restrição que não se aplica mais. Os nomes lógicos de tabela definidos na ADR-0003 são mantidos como sufixo; apenas o prefixo de catálogo e schema muda.
- **ADR-0006**: esta ADR é complementar à ADR-0006. Os Volumes definidos em ADR-0006 (`main/default/bronze/`, `main/default/silver/`, `main/default/gold/`) são o `LOCATION` das tabelas externas registradas aqui. As duas decisões devem ser lidas em conjunto.
- **ADR-0002** (MERGE INTO): a chave de upsert `(serie_id, data)` e a lógica de MERGE permanecem inalteradas. A mudança de Hive Metastore para Unity Catalog afeta apenas o nome de referência da tabela destino no comando `MERGE INTO main.default.bronze_bcb`.
- **ADR-0005** (assertions Python): as assertions que referenciam tabelas por nome lógico devem usar o nome totalmente qualificado (`main.default.silver_bcb`). A lógica de validação permanece inalterada.

## Revisão
Elaborado por: Claude (Agente IA) — arquiteto-dados
Data/hora: 2026-07-22 03:30 BRT

## Aprovação
Aprovado por: Lucas de Araújo
Data/hora: 2026-07-22 16:10 BRT
