# RFC — Banco simples com saldo consistente, limites e pricing explícito

**TIME:** `<Vinicius Drexler e Wallace Teixeira>`
**DATA:** 09/10/2026
**VERSÃO:** 1

## Contextualização

### Entendendo o problema

A entrega cadastra cliente, abre conta, recebe funding confirmado, transfere dinheiro com tarifa e
oferece extrato. O problema difícil é garantir que dinheiro não seja criado, perdido ou cobrado
duas vezes quando requisições falham, repetem ou concorrem. Também precisamos impedir movimentação
por conta bloqueada/encerrada, aplicar limites de risco e fazer o extrato explicar o saldo. O MVP
atende PF adulta, uma conta por cliente e monetiza transferências concluídas. Pix real, cartão,
crédito, frontend, KYC externo e approval workflow de limites ficam fora do escopo.

### Explicando a solução de forma macro

Uma API FastAPI preserva as camadas do `bootcamp-base-api` e usa PostgreSQL. UUIDs são públicos e
dinheiro é inteiro em centavos. A conta guarda saldo, status e limites; `bank_transaction` registra
fatos append-only de `deposit`, `transfer` e `fee`. Funding exige uma referência externa única.
Transferências travam as contas em ordem determinística, resolvem replay, validam status, limites e
saldo e persistem débito, crédito e tarifa antes de um único commit. A tarifa vem de uma política
de billing persistida; a versão base usa `fixed_amount=R$2`. Saldo calculado sempre pelo histórico
foi descartado pelo custo de leitura; tabelas separadas por tipo complicariam o extrato;
microserviços e integrações financeiras reais adicionariam complexidade sem necessidade nesta
entrega.

## Implementação

### Rotas

| Método | Caminho | O que faz | Entrada relevante | Saídas |
|---|---|---|---|---|
| POST | `/client` | cria cliente | nome, CPF, nascimento | `201`; `400`; `409`; `422` |
| GET | `/client/{client_key}` | consulta cliente próprio | `X-CLIENT-KEY` | `200`; `401`; `404` |
| POST | `/client/{client_key}/account` | abre conta ativa com saldo zero | `X-CLIENT-KEY` | `201`; `401`; `404`; `409` |
| GET | `/account/{account_key}` | consulta saldo/status/limites | `X-CLIENT-KEY` | `200`; `401`; `404` |
| PUT | `/account/{account_key}/limits` | configura limites internos | limite unitário e diário | `200`; `400`; `404`; `422` |
| PUT | `/webhook/account/{account_key}/status` | aplica evento de status | `active/blocked/closed` | `200`; `400`; `404`; `409` |
| GET | `/billing_configuration/transfer` | consulta política comercial | — | `200`; `403` |
| PUT | `/billing_configuration/transfer` | altera pricing de novas transferências | tarifa fixa ou percentual | `200`; `400`; `403` |
| POST | `/account/{account_key}/transaction` | depósito ou transferência | request key, tipo, valor e campos condicionais | `201`; `400`; `404`; `409`; `422`; `423` |
| GET | `/account/{account_key}/transactions` | extrato paginado | `limit`, `page` | `200`; `400`; `401`; `404` |

Operações financeiras são idempotentes por `request_control_key`. Repetir a mesma chave e o mesmo
pedido devolve o mesmo resultado; reutilizar a chave com outro pedido retorna `409`. Depósito exige
também `funding_reference` única para que o mesmo funding não seja aplicado com outra request key.

### Banco de Dados (Somente diagrama)

```mermaid
erDiagram
    CLIENT ||--|| ACCOUNT : owns
    ACCOUNT_STATUS ||--o{ ACCOUNT : current_status
    ACCOUNT ||--o{ ACCOUNT_STATUS_EVENT : status_history
    ACCOUNT_STATUS ||--o{ ACCOUNT_STATUS_EVENT : event_status
    TRANSACTION_TYPE ||--o{ BANK_TRANSACTION : classifies
    ACCOUNT ||--o{ BANK_TRANSACTION : origin
    ACCOUNT ||--o{ BANK_TRANSACTION : destination

    CLIENT {
        BIGINT id PK
        UUID client_key UK
        STRING document_number UK
        DATE birth_date
    }
    ACCOUNT {
        BIGINT id PK
        UUID account_key UK
        BIGINT client_id FK_UK
        INT status_id FK
        BIGINT balance
        BIGINT single_transfer_limit
        BIGINT daily_transfer_limit
    }
    ACCOUNT_STATUS {
        INT id PK
        STRING enumerator UK
    }
    ACCOUNT_STATUS_EVENT {
        BIGINT id PK
        BIGINT account_id FK
        INT status_id FK
        TIMESTAMP event_datetime
    }
    TRANSACTION_TYPE {
        INT id PK
        STRING enumerator UK
    }
    BANK_TRANSACTION {
        BIGINT id PK
        UUID transaction_key UK
        UUID operation_key
        UUID request_control_key UK
        UUID external_reference UK
        INT type_id FK
        BIGINT origin_account_id FK
        BIGINT destination_account_id FK
        BIGINT amount
    }
    BILLING_CONFIGURATION {
        BIGINT id PK
        STRING operation_type UK
        STRING expense_type
        BIGINT fixed_amount_cents
        INT percentage_basis_points
    }
```

### Fluxos

**Transferência — caminho feliz**

1. Middleware valida `INTERNAL-TOKEN`; controller valida identidade da origem.
2. Origem e destino são travados com `FOR UPDATE` em ordem determinística.
3. O controller resolve replay idempotente antes de regras que podem mudar depois do commit.
4. Ambas as contas precisam estar `active`.
5. `amount` precisa caber no limite por operação e no limite diário restante.
6. A política de billing vigente calcula a tarifa; no MVP base, `fixed_amount=200` centavos.
   A política pode ser fixa ou percentual para novas operações, sem reescrever fees históricas.
7. O saldo precisa cobrir `amount + fee`.
8. Origem é debitada, destino creditado e `transfer` + `fee` são gravados com a mesma `operation_key`.
9. `flush()` materializa constraints e o controller executa um único `commit()`.

**Transferência — falha por limite ou saldo**

1. A conta já está travada quando a regra é avaliada.
2. Limite por operação excedido retorna `422 QIT004004`; limite diário, `422 QIT004005`;
   saldo insuficiente, `422 QIT004001`.
3. Nenhum saldo, transferência ou tarifa é persistido.

**Depósito confirmado — retry/funding duplicado**

1. A conta é travada e o replay por `request_control_key` é resolvido.
2. A conta precisa estar ativa.
3. `funding_reference` identifica o evento externo confirmado e é única.
4. Reutilizar a mesma funding reference com outra request key retorna `409 QIT004006` e não
   aumenta o saldo novamente.

**Status e limites**

Configuração de limite é uma operação interna e idempotente. Eventos internos podem bloquear,
reativar ou encerrar a conta; `closed` é final e exige saldo zero. Contas não ativas não movimentam
dinheiro.

**Principal desafio**

**Qual é:** preservar consistência financeira sob concorrência, retry e regras operacionais mutáveis.
**Por que é difícil:** duas requisições podem decidir usando o mesmo saldo; retries podem repetir
efeitos; status, limites e pricing podem mudar depois de uma operação já concluída.
**Como o desenho resolve:** locks em ordem determinística, validação sob lock, idempotência no
banco, funding reference única, replay antes de regras mutáveis, histórico append-only e um único
commit para todos os efeitos financeiros.
