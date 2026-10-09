# Contrato da API bancária — v0.1

Todas as rotas, exceto `/` e `/health_check`, continuam protegidas pelo `INTERNAL-TOKEN` do
projeto-base. Rotas que leem/criam recursos de um cliente também recebem `X-CLIENT-KEY`,
considerado uma identidade já autenticada por um gateway confiável.

Dinheiro é sempre inteiro em centavos.

## POST /client

```json
{
  "name": "Ana Souza",
  "document_number": "529.982.247-25",
  "birth_date": "1994-03-12"
}
```

`201`:

```json
{"client_key": "uuid"}
```

Erros relevantes: `400` schema, `409` CPF duplicado, `422` CPF inválido/data impossível/menor.

## GET /client/{client_key}

Headers: `INTERNAL-TOKEN`, `X-CLIENT-KEY`.

`200` devolve `client_key`, nome, CPF, data de nascimento e `created_at`.
Cliente alheio e inexistente respondem `404`.

## POST /client/{client_key}/account

Sem corpo. Headers: `INTERNAL-TOKEN`, `X-CLIENT-KEY`.

`201`:

```json
{"account_key": "uuid"}
```

O saldo nasce em zero. Um cliente pode abrir mais de uma conta neste MVP.

## GET /account/{account_key}

`200`:

```json
{
  "account_key": "uuid",
  "client_key": "uuid",
  "balance": 29800,
  "created_at": "..."
}
```

Conta alheia e inexistente respondem `404`.

## POST /account/{account_key}/transaction — depósito

```json
{
  "request_control_key": "uuid",
  "type": "deposit",
  "amount": 50000
}
```

`201`: operação criada ou replay idempotente da mesma operação.

## POST /account/{account_key}/transaction — transferência

```json
{
  "request_control_key": "uuid",
  "type": "transfer",
  "amount": 20000,
  "destination_account_key": "uuid"
}
```

A origem paga `amount + 200`; o destino recebe `amount`. A resposta informa `fee_amount: 200`.

Erros relevantes:

- `400`: contrato inválido;
- `404`: origem/destino inexistente ou origem não pertence ao cliente autenticado;
- `409 QIT004002`: origem = destino;
- `409 QIT004003`: request_control_key reutilizada com outro pedido;
- `422 QIT004001`: saldo insuficiente.

## GET /account/{account_key}/transactions?limit=20&page=0

`200`:

```json
{
  "data": [
    {
      "transaction_key": "uuid",
      "operation_key": "uuid",
      "type": "fee",
      "direction": "debit",
      "amount": 200,
      "balance_effect": -200,
      "counterparty_account_key": null,
      "created_at": "..."
    }
  ],
  "limit": 20,
  "page": 0,
  "is_last_page": true
}
```

O extrato é ordenado por `created_at DESC, id DESC`. `limit` aceita 1..100.
