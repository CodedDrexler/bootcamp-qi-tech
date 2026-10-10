# Banco — Bootcamp QI Tech 2026

API bancária desenvolvida sobre o `bootcamp-base-api`, preservando a
arquitetura e as camadas propostas durante o Bootcamp QI Tech.

A solução implementa o núcleo de uma conta bancária para pessoa física:
cadastro de cliente, abertura de conta, entrada de recursos confirmada,
transferência entre contas, cobrança de tarifa e extrato paginado.

Além do escopo mínimo, o projeto incorpora garantias de consistência
financeira, idempotência, concorrência, limites de risco, estados de conta
e configuração da política de tarifa.

---

## Objetivo

O objetivo é construir o menor core bancário capaz de garantir que:

- dinheiro não seja criado ou perdido por uma falha parcial;
- uma transferência não seja executada pela metade;
- duas requisições concorrentes não gastem o mesmo saldo;
- retries não dupliquem depósitos, transferências ou tarifas;
- o saldo nunca fique negativo;
- o histórico financeiro permita explicar o saldo da conta;
- um cliente não consiga operar recursos pertencentes a outro cliente.

O projeto prioriza consistência, clareza do contrato e simplicidade
arquitetural.

---

## Escopo da entrega

### Requisitos centrais

- cadastro e consulta de cliente;
- conta vinculada ao cliente;
- controle de saldo;
- depósito;
- transferência entre contas;
- tarifa de transferência;
- extrato paginado;
- execução com Docker Compose;
- testes black-box com pytest;
- documentação/RFC da solução.

### Capacidades adicionais implementadas

- idempotência financeira;
- proteção contra concorrência e double-spend;
- limites por transferência e por dia;
- estados `active`, `blocked` e `closed`;
- política de billing configurável;
- prevenção de duplicação de funding externo;
- ownership dos recursos;
- códigos de erro estáveis;
- correlação de requisições com `X-Request-ID`.

---

## Fora do escopo

Não fazem parte deste MVP:

- Pix real;
- TED real;
- cartão;
- crédito;
- investimentos;
- frontend;
- KYC externo;
- gateway de autenticação;
- filas;
- Redis;
- microsserviços;
- Kubernetes;
- infraestrutura cloud.

---

## Arquitetura

O projeto mantém a organização do `bootcamp-base-api`.

```text
request
  ↓
middleware
  ↓
schema
  ↓
resource
  ↓
controller
  ↓
repository
  ↓
model / PostgreSQL
  ↓
DTO
  ↓
response
