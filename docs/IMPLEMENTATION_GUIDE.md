# Execução prática — do baseline verde ao banco

O baseline oficial foi confirmado com **35 testes verdes** antes destas alterações.

## Ordem de implementação usada

1. `database/database.sql`: tabelas `client`, `account`, `transaction_type`, `bank_transaction`.
2. `src/models/`: espelho exato dessas tabelas.
3. `src/repositories/`: somente queries, inserts, atualizações de saldo e locks.
4. `src/controllers/`: CPF/idade, ownership, saldo, tarifa, atomicidade e idempotência.
5. `src/schemas/`: contrato de cliente, transação e paginação.
6. `src/resources/`: HTTP e status code.
7. `src/app.py`: registro das seis rotas.
8. `tests/utils/`: helpers HTTP; nenhum import de `src`.
9. `tests/integration/`: casos black-box.

## Primeiro teste no PC depois de aplicar o código

Como `database.sql` mudou, o banco que já está rodando NÃO ganha as tabelas novas sozinho.
Neste projeto descartável de desenvolvimento:

```powershell
docker compose down -v
docker compose up --build -d
docker compose ps
```

Espere `api` e `db` ficarem `healthy`.

Depois, no venv Python 3.11:

```powershell
$env:SERVER_LOCALHOST="localhost"
python -m pytest -v
```

A expectativa desta versão é **79 testes coletados**: 35 originais + 44 bancários.

## Testes focados durante correção

```powershell
python -m pytest -v tests/integration/client
python -m pytest -v tests/integration/account
python -m pytest -v tests/integration/transaction/test_deposit.py
python -m pytest -v tests/integration/transaction/test_transfer.py
python -m pytest -v tests/integration/statement
```

O teste crítico de concorrência deve ser repetido no PostgreSQL real:

```powershell
1..20 | ForEach-Object {
  python -m pytest -q tests/integration/transaction/test_transfer.py::TestTransfer::test_two_concurrent_transfers_cannot_spend_same_balance
  if ($LASTEXITCODE -ne 0) { break }
}
```

E o replay concorrente:

```powershell
1..20 | ForEach-Object {
  python -m pytest -q tests/integration/transaction/test_transfer.py::TestTransfer::test_two_concurrent_replays_execute_only_once
  if ($LASTEXITCODE -ne 0) { break }
}
```

## Regra de trabalho daqui em diante

Teste vermelho reproduzível -> corrigir a menor causa -> suíte focada -> suíte inteira -> commit.
Não empilhar três features quebradas na mesma branch.

## Gate automatizado no Windows

Com o venv 3.11 ativo, todo o fluxo acima pode ser executado por:

```powershell
.\scripts\final_gate.ps1
```

Ele recria os containers, roda a suíte inteira e repete 20 vezes cada um dos dois testes
concorrentes críticos. Use-o somente neste ambiente descartável de desenvolvimento.
