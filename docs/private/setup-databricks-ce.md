# Guia de Setup — Azure Databricks (Trial)

> Arquivo privado (gitignored). Não commitar.
> Atualizado em 2026-07-22.
> Plataforma: Azure Databricks com conta gratuita Azure ($200 de crédito).

---

## Contexto de custo

- Azure conta gratuita: $200 de crédito por 30 dias
- Cobrança de $1 temporária no cartão durante verificação (estornada automaticamente)
- Cluster Standard_DS3_v2 (4 cores, 14GB): ~$0.25/h em VMs Azure
- Para ~15h de trabalho: custo estimado de **$5–10 em créditos** (sem sair do bolso)
- **Regra de ouro:** encerrar (Terminate) o cluster ao final de cada sessão

---

## 1. Criar conta Azure gratuita

1. Acessar: https://azure.microsoft.com/free
2. Clicar em **"Experimente gratuitamente"** (ou "Start free")
3. Fazer login com conta Microsoft ou criar uma nova
4. Preencher dados e cadastrar cartão de crédito
   - Cobrança de $1 temporária para verificação — estornada em até 5 dias úteis
5. Confirmar — $200 de crédito disponível por 30 dias

---

## 2. Criar recurso Azure Databricks

1. No portal Azure (portal.azure.com): clicar em **"+ Criar um recurso"**
2. Buscar **"Azure Databricks"** e selecionar
3. Clicar em **Criar**
4. Preencher:
   - **Assinatura:** selecionar a assinatura gratuita
   - **Grupo de recursos:** criar novo → `bcb-lakehouse-rg`
   - **Nome do workspace:** `bcb-lakehouse-databricks`
   - **Região:** `East US` (menor latência e custo)
   - **Tipo de preço:** `Trial` (se disponível) ou `Standard`
5. Clicar em **Revisar + criar** → **Criar**
6. Aguardar o deploy (~3 min) e clicar em **Ir para o recurso**
7. Clicar em **Iniciar workspace** — abre o Databricks

---

## 3. Criar cluster

1. No Databricks: menu lateral → **Compute** → **Create compute**
2. Configurações:
   - **Cluster name:** `bcb-cluster`
   - **Databricks Runtime:** `14.3 LTS` (Spark 3.5, Delta Lake 3.x)
   - **Node type:** `Standard_DS3_v2` (4 cores, 14GB — menor custo razoável)
   - **Auto-terminate:** `60 minutes`
3. Clicar em **Create compute**
4. Aguardar status **Running** (3–5 min)

---

## 4. Conectar repositório GitHub (Databricks Repos)

### 4.1 Gerar token do GitHub

1. GitHub: **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. **Generate new token (classic)** → escopo: `repo`
3. Copiar o token (aparece uma única vez)

### 4.2 Configurar credencial no Databricks

1. Canto superior direito → ícone do usuário → **User Settings**
2. **Linked accounts** → **Git integration**
3. Preencher:
   - **Git provider:** GitHub
   - **GitHub username:** seu usuário
   - **Personal access token:** colar o token
4. Salvar

### 4.3 Criar repositório no GitHub

1. Criar repositório público: `bcb-lakehouse-databricks`
2. Não inicializar com README

### 4.4 Inicializar e subir o repo local

No Git Bash, dentro de `C:\claude_jobs\bcb-lakehouse-databricks\`:

```bash
git init
git add .
git commit -m "feat: estrutura inicial, ADRs 0000-0005 e cronograma"
git remote add origin https://github.com/<seu-usuario>/bcb-lakehouse-databricks.git
git branch -M main
git push -u origin main
```

### 4.5 Importar no Databricks Repos

1. Menu lateral → **Repos** → **Add repo**
2. Colar URL do repositório GitHub
3. **Create repo**
4. Repositório disponível em `/Repos/<seu-email>/bcb-lakehouse-databricks/`

---

## 5. Verificar acesso à API do BCB

Criar um notebook temporário e executar:

```python
import requests

url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados?formato=json&dataInicial=01/01/2026&dataFinal=31/01/2026"
response = requests.get(url, timeout=10)

print(f"Status: {response.status_code}")
print(f"Primeiros registros: {response.json()[:3]}")
```

**Esperado:** `Status: 200` com registros JSON. Se OK, deletar o notebook temporário.

---

## 6. Criar estrutura DBFS (ADR-0001)

```python
dbutils.fs.mkdirs("/delta/bronze/bcb/")
dbutils.fs.mkdirs("/delta/silver/bcb/")
dbutils.fs.mkdirs("/delta/gold/")

display(dbutils.fs.ls("/delta/"))
```

**Esperado:** listagem com `bronze/`, `silver/` e `gold/`.

---

## 7. Checklist de conclusão (Fase 2)

- [ ] Conta Azure gratuita criada com $200 de crédito
- [ ] Grupo de recursos `bcb-lakehouse-rg` criado
- [ ] Workspace `bcb-lakehouse-databricks` provisionado no Azure
- [ ] Cluster `bcb-cluster` criado com Runtime 14.3 LTS, status Running
- [ ] Auto-terminate configurado para 60 minutos
- [ ] Repositório GitHub criado e código local pushado
- [ ] Repo conectado no Databricks Repos
- [ ] Chamada de teste para API BCB retorna status 200
- [ ] Caminhos DBFS `/delta/bronze/`, `/delta/silver/`, `/delta/gold/` criados

---

## Controle de custos

- **Sempre encerrar o cluster** ao final de cada sessão: Compute → cluster → **Terminate**
- O auto-terminate de 60 min é um seguro, não a regra
- Verificar uso de créditos: portal.azure.com → **Cost Management + Billing**
- Criar alerta de orçamento: Cost Management → Budgets → alerta em $50 de crédito consumido
