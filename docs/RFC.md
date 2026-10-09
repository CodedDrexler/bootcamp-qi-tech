# RFC — Banco simples com saldo consistente e extrato auditável

**Versão:** 0.1 — documento vivo durante a implementação.

## 1. Contextualização

### Entendendo o problema

O desafio exige cadastrar cliente, vincular contas, movimentar dinheiro com controle de saldo,
cobrar tarifa de transferência e oferecer extrato paginado. As falhas mais caras não são apenas
"endpoint fora do ar": são dinheiro duplicado após retry, saldo negativo por corrida, tarifa
cobrada sem transferência, débito sem crédito e um extrato incapaz de explicar o saldo.

As garantias escolhidas são:

- dinheiro nunca usa float;
- toda operação financeira é atômica;
- saldo nunca fica negativo;
- todo efeito financeiro aparece no histórico;
- retry da mesma requisição não repete efeitos;
- uma conta só pode ser operada por seu titular;
- IDs internos nunca aparecem no contrato externo.

Fora de escopo: frontend, Pix real, cartão, boleto, crédito, filas e infraestrutura de cloud.

### Explicando a solução de forma macro

Uma API FastAPI usa PostgreSQL e preserva as camadas do `bootcamp-base-api`. `client` tem UUID
público e CPF único. `account` pertence a um cliente, guarda `balance BIGINT` em centavos e
permite relação 1:N. `bank_transaction` é append-only e registra `deposit`, `transfer` e `fee`.

Transferência trava as contas em ordem determinística (`FOR UPDATE`), verifica o saldo já sob
lock, debita origem, credita destino, grava transferência e tarifa e só então faz um commit.
A tarifa do MVP é fixa em R$ 2,00 e existe como linha própria do histórico.

`request_control_key` é única no banco. Mesma chave e mesmo pedido devolvem o resultado já
criado; mesma chave com semântica diferente retorna 409.

`INTERNAL-TOKEN` autentica o serviço chamador. Como ele não identifica o cliente final, a API
recebe `X-CLIENT-KEY` de um gateway confiável e valida ownership no controller.

### Alternativas consideradas

1. **Saldo calculado sempre pelo histórico.** Fonte única, mas leitura mais cara; ganharia em
   um sistema pequeno priorizando auditabilidade sobre leitura frequente.
2. **Tabela por tipo de transação.** Constraints mais específicas, mas extrato vira união de
   tabelas e regras se duplicam; ganharia se os tipos divergissem estruturalmente.
3. **Tarifa apenas diminuindo `balance`.** Uma escrita a menos, mas o extrato não explicaria o
   saldo; rejeitada.
4. **Sem idempotência.** Menos código, mas timeout/retry pode duplicar dinheiro; rejeitada.
5. **JWT dentro desta API.** Resolveria identidade diretamente, mas aumenta escopo. Nesta
   arquitetura o gateway autentica e o core autoriza o recurso.
6. **Máquina de estados de conta agora.** A aula apresenta CREATED/ACTIVE/BLOCKED/CLOSED, mas
   o MVP ainda não possui comandos de bloqueio/fechamento; criar a tabela agora seria estado
   sem comportamento. Entra quando o produto ganhar essas transições.

## 2. Implementação

### Rotas

| Método | Caminho | Papel |
|---|---|---|
| POST | `/client` | cadastrar cliente |
| GET | `/client/{client_key}` | consultar o próprio cliente |
| POST | `/client/{client_key}/account` | abrir conta |
| GET | `/account/{account_key}` | consultar saldo |
| POST | `/account/{account_key}/transaction` | depósito/transferência |
| GET | `/account/{account_key}/transactions` | extrato paginado |

### Banco de Dados (diagrama)

```text
CLIENT 1 ───── N ACCOUNT
                  │
                  ├──────── origin ───────┐
                  └──── destination ──────┤
                                         ▼
                                BANK_TRANSACTION N ─── 1 TRANSACTION_TYPE
```

`client`: id PK, client_key UK, CPF UK, nome, nascimento.

`account`: id PK, account_key UK, client_id FK, balance BIGINT CHECK >= 0.

`bank_transaction`: transaction_key UK, operation_key, request_control_key UK, tipo, origem,
destino, amount BIGINT > 0, created_at. Não há rota de UPDATE/DELETE para histórico.

### Fluxo feliz — transferência

1. schema valida request_control_key/type/amount/destino;
2. controller verifica identidade;
3. procura replay idempotente;
4. repository trava origem e destino em ordem fixa;
5. controller revalida replay e ownership;
6. confere `origin.balance >= amount + fee`;
7. debita origem e credita destino;
8. grava `transfer` e `fee` com a mesma `operation_key`;
9. `flush()` materializa constraints;
10. controller faz um único `commit()`;
11. resource devolve 201.

### Falhas importantes

- saldo insuficiente: 422 e nenhuma escrita persiste;
- destino inexistente: 404 e origem não muda;
- origem = destino: 409;
- replay idêntico: 201 com o mesmo resultado e zero novo efeito;
- mesma idempotency key com outro pedido: 409;
- conta alheia: 404 para não confirmar existência;
- corrida de saldo: o segundo fluxo espera o lock e reavalia saldo.

### Principal desafio

**Concorrência sem perder a explicabilidade do dinheiro.** O saldo materializado torna a leitura
barata, mas cria risco de duas requisições decidirem usando o mesmo saldo antigo. A solução é
pessimistic locking no PostgreSQL, com ordem determinística para duas contas, e a fronteira da
transação SQL envolve saldo + histórico + tarifa. A suíte deve provar o caso com duas
requisições simultâneas e repetir esse teste no PostgreSQL real antes da entrega.
