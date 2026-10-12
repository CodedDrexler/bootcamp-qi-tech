# Entrega: Porquinho Bank

Protótipo bancário do Bootcamp QI Tech 2026. Entrega em 13/10/2026.

| Exigência | Decisão verificável |
|---|---|
| Cliente | Nome, CPF válido e único, e-mail único, nascimento, maioridade |
| Conta | Uma conta por cliente, UUID público, saldo em centavos, encerramento sem saldo |
| Transação | Depósito, saque e transferência atômicos, sem saldo negativo |
| Tarifa | R$ 1,00 por transferência; cobrança junto ao principal, histórico separado |
| Extrato | Lançamentos imutáveis, ordenação determinística, paginação e saldo após lançamento |
| Diferencial | Porquinhos com nome, meta, reserva e resgate; sem rendimento fictício |
| Segurança | INTERNAL-TOKEN nas rotas de negócio; segredo via ambiente |
| Retentativa | Idempotency-Key obrigatório em POST, UNIQUE(scope, key), mesma resposta |
| Concorrência | Travas de contas em ordem de id; operações de porquinho travam primeiro a conta |
| Observabilidade | Request ID, logs sem dados pessoais, métricas e plano de alarmes |
| Execução | Python + FastAPI + PostgreSQL; Docker Compose; pytest por HTTP real |
| RFC | PDF seguindo os títulos do modelo, diagrama ER e fluxos com falhas |

O serviço é uma API interna de demonstração. Não liquida dinheiro real, não oferece Pix,
boletos, crédito, juros ou autenticação de correntistas. Não depende de serviços externos:
CPF é validado localmente; logo não há chamada externa para impor timeout nem Mockserver.
As tarifas e depósitos têm contrapartidas contábeis identificadas no diário.

Plano de commits: contratos e testes; modelo e implementação; ambiente e observabilidade;
validação dos fluxos e concorrência; documentação e RFC final.
