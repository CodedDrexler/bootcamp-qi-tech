# Registro vivo de decisões — Bootcamp QI Tech 2026

Este arquivo é a memória arquitetural da dupla. Ele existe para que uma decisão tomada hoje
não vire uma suposição amanhã. A RFC é o documento de defesa da solução; aqui guardamos a
versão curta e operacional de cada escolha enquanto implementamos.

## D01 — Preservar a arquitetura do `bootcamp-base-api`

**Decisão:** manter `resource -> controller -> repository -> model/banco`, com JSON Schema na
entrada, DTO na saída, erros QIT e `commit()` no controller.

**Motivo:** é a arquitetura ensinada e fornecida pela QI Tech. Reescrever infraestrutura agora
aumentaria risco e dificultaria a correção.

## D02 — Uma API FastAPI + um PostgreSQL

**Decisão:** não criar microserviços, filas, cache ou frontend nesta fase.

**Alternativa descartada:** separar `clients-api`, `accounts-api` e `transfers-api`.
**Quando venceria:** times maiores, contratos independentes, deploy/escala separados.

## D03 — Rotas orientadas a recurso

- `POST /client`
- `GET /client/{client_key}`
- `POST /client/{client_key}/account`
- `GET /account/{account_key}`
- `POST /account/{account_key}/transaction`
- `GET /account/{account_key}/transactions?limit=&page=`

A ação fica no método HTTP e o caminho nomeia recursos.

## D04 — Cliente pessoa física e regra mínima de idade

**Decisão:** cliente tem `name`, `document_number` (CPF) e `birth_date`; CPF é válido e único;
idade mínima de 18 anos.

**Observação:** a idade mínima é decisão de produto do grupo, não requisito fixo da QI Tech.
Não existe limite máximo de idade.

## D05 — Cliente pode ter várias contas

**Decisão:** relação `client 1:N account`; `account.client_id` é a FK e NÃO é `UNIQUE`.

**Motivo:** segue a relação N:1 ensinada na Aula 2 e evita impor um limite sem necessidade.

## D06 — Conta nasce ativa por definição do MVP, sem máquina de estados

**Decisão:** nesta primeira entrega não existem bloqueio/encerramento, portanto não criamos
`account_status` só para armazenar um único estado possível.

**Alternativa descartada:** `CREATED -> ACTIVE -> BLOCKED -> CLOSED` + eventos.
**Quando venceria:** quando o produto tiver operações de bloqueio/encerramento e suas regras.

## D07 — Dinheiro em centavos inteiros

**Decisão:** `BIGINT` no banco e `int` nos contratos. Nunca `float`.

Ex.: R$ 200,00 = `20000`.

## D08 — Saldo materializado na conta + histórico append-only

**Decisão:** `account.balance` fornece leitura barata; `bank_transaction` registra cada fato.
O histórico nunca é atualizado ou apagado pelas rotas do domínio.

**Invariante:** para uma conta criada com saldo zero, a soma de `balance_effect` do extrato
deve reconstruir o saldo atual.

**Alternativa:** calcular saldo sempre pela soma do histórico. Eliminaria a duplicidade de
representação, mas deixaria toda leitura mais cara.

## D09 — Uma tabela de transações com tipos `deposit`, `transfer`, `fee`

**Decisão:** uma única tabela `bank_transaction` com `transaction_type`.

**Motivo:** o extrato é uma única consulta; a tarifa é um fato financeiro visível.

**Alternativa:** tabela por tipo de operação. Venceria se cada tipo tivesse estrutura muito
diferente e constraints específicas compensassem o custo de unir o extrato.

## D10 — Tarifa fixa de 200 centavos por transferência concluída

**Decisão:** uma transferência bem-sucedida debita `amount + 200` da origem, credita `amount`
no destino e grava uma linha `fee` de 200 centavos.

**Importante:** é decisão do grupo, inspirada no exemplo de R$ 200 + R$ 2 usado em aula.
Falha e replay idempotente não cobram tarifa.

## D11 — Atomicidade: um único commit por operação financeira

Depósito: saldo + linha de depósito pertencem à mesma transação SQL.

Transferência: débito da origem + crédito do destino + linha transfer + linha fee pertencem à
mesma transação SQL. Qualquer erro antes do commit provoca rollback pelo middleware.

## D12 — Concorrência: `SELECT ... FOR UPDATE` e ordem determinística

**Decisão:** operações financeiras travam as contas envolvidas. Quando há duas contas, as keys
são ordenadas antes do lock para reduzir risco de deadlock em operações A->B e B->A.

Saldo é verificado somente depois do lock.

## D13 — Idempotência faz parte do contrato

**Decisão:** todo POST financeiro exige `request_control_key` UUID no corpo.

- mesma chave + mesmo pedido -> mesma resposta, sem novo efeito;
- mesma chave + pedido diferente -> `409 QIT004003`;
- `UNIQUE(request_control_key)` é a última garantia no banco;
- a aplicação reconsulta depois do lock para tratar replay concorrente.

## D14 — Identidade e ownership (R8)

`INTERNAL-TOKEN` autentica o **serviço chamador**. Ele não identifica o cliente final.

**Decisão desta API interna:** um gateway confiável autentica o cliente e encaminha sua
identidade em `X-CLIENT-KEY`. A API sempre confere no banco se o recurso pertence àquela
identidade. Recurso alheio responde 404, não 403, para não confirmar existência.

**Atenção:** `X-CLIENT-KEY` não é uma senha e não pode ser aceito diretamente da internet sem
um gateway que o sobrescreva/garanta.

## D15 — Paginação do extrato

- `limit`: 1..100, padrão 20;
- `page`: >= 0, padrão 0;
- ordenação: `created_at DESC, id DESC`;
- consulta pede `limit + 1` para calcular `is_last_page`.

## D16 — O que fica fora do MVP

Frontend, Pix real, boleto, cartão, empréstimo, filas, Redis, Kubernetes, autoscaling real,
webhooks financeiros, fechamento/bloqueio de conta e integrações externas. Conceitos de
produção da Aula 4 entram como decisões/boas práticas, sem fingir infraestrutura inexistente.
