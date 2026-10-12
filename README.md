# Porquinho Bank

Banco de demonstração do **Bootcamp QI Tech 2026**, por **Vinicius e Wallace**.
Clientes, contas, depósitos, saques, transferências com tarifa e extrato paginado,
com porquinhos para organizar reservas e metas. API interna em Python + FastAPI,
PostgreSQL 16 e Docker.

## Rodar

Instale Docker com Compose e Git. Clone este repositório, abra a pasta e rode:

```sh
docker compose up --build --wait
```

A API atende em http://127.0.0.1:3000. `GET /health_check` retorna 204 sem depender
do banco. Dados permanecem no volume `bank_data`. Para parar: `docker compose down`.
Se uma porta estiver ocupada, copie `.env.example` para `.env` e ajuste API_PORT/DB_PORT.
Ao trocar DB_PORT, ajuste também DATABASE_URL para os testes fora do container.

O token local é `default_token`; vem de variável de ambiente. É apenas uma configuração
de demonstração. O serviço não liquida dinheiro real e não autentica correntistas.

## Testar e demonstrar

Python 3.11 ou superior, com a API e um **banco exclusivo de testes** de pé:

```sh
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v
python scripts/demo.py
```

Os testes originais zeram o schema do banco em cenários de listagem: não use um banco
com dados que deseja preservar. Os novos cenários são montados por HTTP. Sete testes
adicionais verificam restrições do PostgreSQL; o teste de timeout espera cerca de 5s.
A suíte não importa src/ e inclui 70 testes: 35 originais e 35 de banco/integridade.
A demonstração cria clientes sintéticos novos a cada execução e não apaga dados.
Resultado: depósito R$ 100,00; reserva R$ 40,00; transferência R$ 25,00; tarifa R$ 1,00;
origem disponível R$ 34,00, reserva R$ 40,00 e destino R$ 25,00.

`BANK_API_URL` permite escolher o endereço da nova suíte e da demonstração. Sem ele,
os testes usam SERVER_LOCALHOST e API_PORT. O `.env` é lido pelo pytest.

## Contrato

Todo POST de negócio exige `INTERNAL-TOKEN`, `Content-Type: application/json` e
`Idempotency-Key`. A chave é ASCII, tem 1..128 caracteres e aceita letras, números,
ponto, dois-pontos, underscore e hífen. Repetir chave + corpo retorna o sucesso original;
mudar o corpo retorna 409. Falhas não consomem a chave. Valores monetários são
**inteiros em centavos de BRL**; R$ 10,50 é `1050`, nunca `10.50` ou `1050.0`.

Exemplo no PowerShell, com a API de pé:

```powershell
$headers = @{ 'INTERNAL-TOKEN'='default_token'; 'Idempotency-Key'=[guid]::NewGuid().ToString() }
$body = @{ name='Cliente Exemplo'; email='cliente@example.test'; document_number='529.982.247-25'; birthdate='1990-05-17' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:3000/customers' -Headers $headers -ContentType 'application/json' -Body $body
```

| Recurso | Operações |
|---|---|
| `/customers` | POST cadastro e GET lista |
| `/customers/{customer_key}` | GET cliente |
| `/accounts` | POST conta e GET lista |
| `/accounts/{account_key}` | GET saldos e PATCH `{ "status": "CLOSED" }` |
| `/accounts/{account_key}/transactions` | POST depósito/saque/transferência e GET extrato |
| `/accounts/{account_key}/piggy_banks` | POST porquinho e GET lista |
| `/accounts/{account_key}/piggy_banks/{piggy_bank_key}` | GET porquinho e PATCH encerramento |
| `/accounts/{account_key}/piggy_banks/{piggy_bank_key}/transactions` | POST reserva/resgate e GET extrato |
| `/metrics` | GET métricas, com token |

Transação de conta: `{ "type": "DEPOSIT", "amount": 10000 }`, `WITHDRAWAL` ou
`TRANSFER`; só transferência exige `destination_account_key`. Porquinho:
`{ "name": "Viagem", "target_amount": 4000 }`. Movimento de reserva:
`{ "type": "SAVE", "amount": 4000 }` ou `REDEEM`.
Listas e extratos: `?limit=10&page=0`, teto 100, ordem mais recente primeiro.
Saldo disponível exclui reservas. Extrato da conta exclui o bolso do porquinho:
cada um reconstrói seu próprio saldo. A meta não limita saldo nem bloqueia resgate.

CPF/e-mail e conta por cliente são únicos. Nome de porquinho é único por conta,
inclusive após encerramento. Só se encerra conta com disponível e reservas zerados;
só se encerra porquinho vazio. Leituras históricas continuam disponíveis.
Transferência custa 100 centavos adicionais à origem, registrados como FEE no extrato.
Erros têm `title`, `description`, `translation`, `code` e status próprio. O RFC detalha
cada rota, falha, regra e decisão.

## Documentação da entrega

- [RFC em PDF](output/pdf/RFC-Porquinho-Bank.pdf)
- [RFC editável com modelo ER](docs/rfc.md)
- [Operação, alarmes e limites](docs/operacao.md)
- [Critérios da entrega](docs/entrega.md)
- [Organização das camadas da base](docs/como-o-projeto-e-organizado.md)
- [README original da base e rotas sample_entity](docs/base-readme.md)

A implementação preserva resources → controllers → repositories → models, com
schemas, DTOs e errors separados. Idempotência e travas ficam no PostgreSQL, funcionando
entre réplicas. O diário usa contrapartidas e gatilhos diferidos: saldo e extrato precisam
bater no commit, e histórico não pode ser alterado. Essa conferência custa mais com
histórico grande; a escolha e sua evolução estão na RFC.

Para monitoramento local opcional: `docker compose --profile observability up --build`.
Prometheus abre em http://127.0.0.1:9090. Veja docs/operacao.md para configuração do token,
alarmes, timeout, escala futura e limites. Não há serviço externo no fluxo bancário.

GitHub Actions monta a imagem, inicia o Compose no Linux e executa a suíte por HTTP.
Uma instalação existente da base deve aplicar `database/migrations/001_bank.sql`
**uma vez**; não remova volumes para migrar. Para reconstruir o PDF: instale
`requirements-docs.txt` e execute `python scripts/build_rfc.py`.
