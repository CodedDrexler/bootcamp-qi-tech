# Banco — Bootcamp QI Tech 2026

API bancária construída sobre o `bootcamp-base-api` fornecido no Bootcamp, preservando sua
estrutura em Python, FastAPI, PostgreSQL, Docker e pytest.

A entrega implementa cadastro de cliente, conta, depósito confirmado, transferência com tarifa,
limites de risco, status de conta e extrato paginado.

## Funcionalidades

- cadastro e consulta de cliente pessoa física;
- uma conta por cliente no MVP;
- saldo inicial zero;
- depósito como entrada de recursos já confirmada por uma fronteira externa;
- transferência interna entre contas;
- tarifa configurável para novas transferências;
- limite por transferência e limite diário por conta;
- status de conta `active`, `blocked` e `closed`;
- extrato append-only, paginado e ordenado;
- idempotência financeira por `request_control_key`;
- proteção contra double-spend com `SELECT ... FOR UPDATE`;
- autorização por ownership;
- erros QIT estáveis e correlação por `X-Request-ID`.

Ficam fora do escopo: Pix real, cartão, crédito, investimentos, frontend, KYC externo,
filas, cache, microserviços e fluxo de aprovação de aumento de limite.

## Arquitetura

O fluxo principal preserva as responsabilidades do serviço-base:

```text
request
  -> middlewares
  -> schema
  -> resource
  -> controller
  -> repository
  -> model/PostgreSQL
  -> DTO
  -> response
```

A regra de negócio fica no controller; repositories cuidam de acesso ao PostgreSQL; models
espelham as tabelas; DTOs controlam a superfície pública.

## Dinheiro e consistência

Valores monetários são inteiros em centavos (`BIGINT` no PostgreSQL). O contrato do MVP aceita
operações individuais de até `100000000` centavos (R$ 1.000.000,00).

A conta mantém saldo materializado e o histórico financeiro é append-only. Transferências:

1. travam origem e destino em ordem determinística;
2. resolvem replay idempotente;
3. validam status, limites e saldo sob lock;
4. calculam a tarifa vigente;
5. persistem débito, crédito, transferência e fee;
6. executam um único `commit`.

A política inicial de tarifa é fixa em R$ 2,00 por transferência concluída. O desenho também
suporta tarifa percentual em basis points, sem `float`.

## Rotas do domínio

| Método | Rota | Função |
|---|---|---|
| POST | `/client` | cadastra cliente |
| GET | `/client/{client_key}` | consulta cliente |
| POST | `/client/{client_key}/account` | abre conta |
| GET | `/account/{account_key}` | consulta saldo, status e limites |
| PUT | `/account/{account_key}/limits` | configura limites internos |
| PUT | `/webhook/account/{account_key}/status` | aplica evento interno de status |
| GET | `/billing_configuration/transfer` | consulta política de tarifa |
| PUT | `/billing_configuration/transfer` | configura tarifa |
| POST | `/account/{account_key}/transaction` | depósito ou transferência |
| GET | `/account/{account_key}/transactions?limit=20&page=0` | extrato |

`/` e `/health_check` são públicos. As demais rotas exigem `INTERNAL-TOKEN`. Recursos de cliente
também usam `X-CLIENT-KEY`, assumindo uma identidade encaminhada por um gateway confiável.

## Executar

Requisitos:

- Docker com Docker Compose;
- Python 3.11.x para a suíte de testes no host.

```bash
docker compose up --build -d
docker compose ps
```

Espere `api` e `db` ficarem `healthy`.

### Testes no PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:SERVER_LOCALHOST="localhost"
python -m pytest -q
```

### Testes no Linux/macOS

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
export SERVER_LOCALHOST=localhost
python -m pytest -q
```

Os testes rodam fora do container, contra a API e o PostgreSQL levantados pelo Docker Compose,
seguindo o formato do projeto-base.

## Documentação

- `docs/RFC.md` — desenho da solução no formato do Bootcamp;
- `docs/API_CONTRACT.md` — contrato HTTP detalhado;
- `docs/ERROR_CATALOG.md` — catálogo de erros;
- `docs/como-o-projeto-e-organizado.md` — material estrutural que já fazia parte do projeto-base.

## Modelo de negócio

A monetização inicial é por uso:

```text
receita de tarifas
=
transferências concluídas × tarifa efetiva
```

Transferências rejeitadas não geram tarifa. Novos produtos podem ampliar a receita por cliente
no futuro, mas permanecem fora desta entrega.
