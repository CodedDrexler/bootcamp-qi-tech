# Banco — Bootcamp QI Tech 2026

Extensão do `bootcamp-base-api` para o desafio de cliente, conta, transações, tarifa e extrato.
A estrutura original foi preservada e os testes `sample_entity` continuam como regressão da base.

## Rodar

```bash
docker compose up --build -d
docker compose ps
```

Depois, com Python 3.11 e `requirements-dev.txt` instalados:

```bash
pytest -v
```

## Contratos e decisões

- `docs/API_CONTRACT.md`
- `docs/DECISIONS.md`
- `docs/RFC.md`
- `docs/IMPLEMENTATION_GUIDE.md`

## Decisões-chave

- dinheiro em centavos inteiros;
- cliente 1:N conta;
- saldo materializado + histórico append-only;
- tarifa fixa de 200 centavos por transferência concluída;
- uma tabela de transações `deposit/transfer/fee`;
- um commit por operação financeira;
- `SELECT ... FOR UPDATE` com ordem determinística;
- `request_control_key` para idempotência;
- ownership conferido usando identidade `X-CLIENT-KEY` encaminhada por gateway confiável.
