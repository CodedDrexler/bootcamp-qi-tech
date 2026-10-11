# Contrato da API bancária — v1

Todas as rotas, exceto `/` e `/health_check`, exigem `INTERNAL-TOKEN`.
Rotas de recursos do cliente também usam `X-CLIENT-KEY`, considerado uma identidade já
autenticada por um gateway confiável.

Dinheiro é inteiro em centavos. O teto técnico de uma operação individual no MVP é
`100000000` centavos (R$ 1.000.000,00).

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

Erros: `400` schema; `409` CPF duplicado; `422` CPF/data/idade.

## GET /client/{client_key}

Headers: `INTERNAL-TOKEN`, `X-CLIENT-KEY`.

`200` devolve `client_key`, nome, CPF, nascimento e `created_at`. Cliente alheio e inexistente
respondem `404`.

## POST /client/{client_key}/account

Sem corpo. Headers: `INTERNAL-TOKEN`, `X-CLIENT-KEY`.

`201`:

```json
{"account_key": "uuid"}
```

A conta nasce com saldo zero, status `active`, limite por transferência de `500000` e limite
diário de `2000000` centavos. Uma segunda conta para o mesmo cliente retorna `409 QIT003002`.

## GET /account/{account_key}

`200`:

```json
{
  "account_key": "uuid",
  "client_key": "uuid",
  "status": "active",
  "balance": 29800,
  "single_transfer_limit": 500000,
  "daily_transfer_limit": 2000000,
  "created_at": "..."
}
```

Conta alheia e inexistente respondem `404`.

## PUT /account/{account_key}/limits

Rota interna de configuração de risco. Não usa `X-CLIENT-KEY`; o chamador já precisa estar dentro
da fronteira protegida por `INTERNAL-TOKEN`.

```json
{
  "single_transfer_limit": 100000,
  "daily_transfer_limit": 500000
}
```

Regras:

- ambos > 0;
- `single_transfer_limit <= 100000000`;
- `daily_transfer_limit >= single_transfer_limit`.

`200` devolve `account_key` e os dois limites. Configuração incoerente retorna `422 QIT003006`.

## PUT /webhook/account/{account_key}/status

Evento interno de status:

```json
{"status": "blocked"}
```

Status aceitos: `active`, `blocked`, `closed`.

- `blocked` e `closed` não operam dinheiro;
- `closed` é final;
- encerramento exige saldo zero.

## GET /billing_configuration/transfer

Rota interna de leitura da política comercial vigente. Exige `INTERNAL-TOKEN` e não usa
`X-CLIENT-KEY`, porque não é uma configuração controlada pelo cliente final.

Política base:

```json
{
  "operation_type": "transfer",
  "expense_type": "fixed_amount",
  "amount": 200
}
```

## PUT /billing_configuration/transfer

Configura a tarifa aplicada **a novas transferências**. Duas formas são aceitas:

```json
{
  "expense_type": "fixed_amount",
  "amount": 250
}
```

ou:

```json
{
  "expense_type": "percentage",
  "percentage_basis_points": 150
}
```

`150` basis points = `1,50%`. O cálculo percentual usa inteiros, arredonda `half-up` para o
centavo e nunca usa `float`. Uma tarifa percentual positiva tem piso técnico de 1 centavo.
Payload ambíguo/incompleto retorna `400 QIT000001`.

Alterar a política não reescreve fatos históricos. Uma `fee` já persistida continua com o valor
original; replay de transferência concluída também devolve a resposta originalmente comprometida.

A configuração é global para o único produto de transferência deste MVP; segmentação comercial
por conta fica fora do escopo desta entrega.

## POST /account/{account_key}/transaction — depósito confirmado

```json
{
  "request_control_key": "uuid",
  "funding_reference": "uuid",
  "type": "deposit",
  "amount": 50000
}
```

`funding_reference` representa a identidade do evento externo já confirmado. Ela é única no banco,
evita que o mesmo funding seja aplicado duas vezes com outra chave de idempotência e não deve ser
interpretada como um rail financeiro implementado neste projeto.

`201`: operação criada ou replay idempotente da mesma operação.

Erros relevantes:

- `400`: schema;
- `409 QIT004003`: `request_control_key` reaproveitada com outro pedido;
- `409 QIT004006`: `funding_reference` já aplicada;
- `423 QIT003003`: conta bloqueada/encerrada.

## POST /account/{account_key}/transaction — transferência

```json
{
  "request_control_key": "uuid",
  "type": "transfer",
  "amount": 20000,
  "destination_account_key": "uuid"
}
```

A tarifa é calculada por `billing_configuration`. Na versão base, a política ativa é
`fixed_amount=200`, portanto a origem paga `amount + 200` e o destino recebe `amount`.

O limite por transferência e o limite diário consideram o `amount` transferido, não a tarifa.

Erros relevantes:

- `400`: contrato inválido;
- `404`: origem/destino inexistente ou origem alheia;
- `409 QIT004002`: origem = destino;
- `409 QIT004003`: chave de idempotência em conflito;
- `422 QIT004001`: saldo insuficiente para `amount + fee`;
- `422 QIT004004`: limite por transferência excedido;
- `422 QIT004005`: limite diário excedido;
- `423 QIT003003`: conta bloqueada/encerrada.

Replay de uma operação já concluída devolve o mesmo resultado mesmo se uma regra mutável, como
status, limite ou pricing, tiver mudado depois do commit original.

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

Ordenação: `created_at DESC, id DESC`. `limit`: 1..100; `page >= 0`.
