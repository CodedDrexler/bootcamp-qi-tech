# Operação e limites

As rotas de negócio pertencem a uma rede interna e usam INTERNAL-TOKEN via ambiente.
Um gateway com identidade e autorização de correntista seria a porta pública de uma
implantação real. Este protótipo não implementa esse gateway e o token não deve ser
enviado a um aplicativo de correntista. As portas do Compose são limitadas ao localhost.

`/health_check` responde 204 sem abrir conexão com o banco. É uma prova de vida do
processo, não de disponibilidade do PostgreSQL. `/metrics` exige o token e expõe
contadores HTTP, histograma de latência e, no Linux, CPU e memória do processo.
Labels usam o padrão da rota, nunca o UUID, CPF ou email. Logs omitem corpo, token e
valores da query; X-Request-ID conecta as linhas de uma requisição. Não há tracing
distribuído: há apenas um serviço e correlação de requisições.

O perfil opcional `docker compose --profile observability up --build` inicia Prometheus
em http://127.0.0.1:9090. Se alterar INTERNAL_TOKEN, ajuste também o header na configuração
local `monitoring/prometheus.yml`. `monitoring/alerts.yml` define limite, janela, dono e ação
para 5xx, p95, CPU e indisponibilidade. As regras aparecem na página Alerts do Prometheus.
Notificações externas exigem um Alertmanager e um destino escolhido pelo operador;
nenhuma mensagem é enviada pela configuração entregue.

Cada conexão espera até 5s para conectar; o pool espera até 5s; a espera por trava é limitada
a 5s e cada comando SQL a 10s. Falhas operacionais do banco retornam 503 QIT002008;
o cliente repete o POST com a mesma Idempotency-Key. Uma resposta 500 indica um defeito
inesperado e deve ser investigada pelo request-id. O connector de boletos herdado da base
tem timeout explícito, mas não é usado neste produto. Não há dependência externa nem
simulação de liquidação real, portanto um Mockserver não participaria de nenhum fluxo.

Na réplica única do Compose as métricas são completas. Em uma implantação com várias
réplicas, colete cada uma separadamente e agregue as séries. Travas e idempotência estão
no PostgreSQL, por isso a correção independe da réplica escolhida pelo balanceador.
Um balanceador deve consultar o health check. Dimensionamento inicial sugerido para
uma implantação futura: mínimo 2, máximo 6 réplicas, ampliar com CPU sustentada acima
de 70% por 5min, reduzir abaixo de 30% por 10min. São parâmetros propostos, não uma
infraestrutura de nuvem instalada. Escalar a API não escala o banco: limite conexões,
monitore bloqueios e meça a carga antes de aumentar o pool.

Os gatilhos recalculam somas do diário para garantir reconciliação e saldo após lançamento.
O custo cresce com o histórico do bolso. Essa escolha privilegia prova de integridade
no protótipo. Em produção de alto volume, a alternativa seria atualização incremental
com permissões SQL mais restritas e reconciliação assíncrona. O papel `bootcamp` é de
desenvolvimento; um deploy real deve separar o papel de migração do papel da aplicação.

O volume `bank_data` preserva dados ao reiniciar os containers. Para um banco já existente,
aplique `database/migrations/001_bank.sql` uma única vez com `psql`; inicialização do
Docker só ocorre em volume novo. Backups e recuperação pontual não são implementados.
Não remova volumes para atualizar o schema. Os testes herdados apagam e recriam o
schema public em cenários de listagem; rode pytest exclusivamente num banco de testes.

Não há expiração de idempotência nesta entrega. Registros de sucesso permanecem no
banco: excluir uma chave financeira permitiria executar novamente um pedido antigo.
Falhas são revertidas, incluindo a chave, e podem ser reavaliadas depois de corrigir
saldo ou indisponibilidade. O replay de sucesso conserva status 201 e corpo original,
mesmo após alterações posteriores de saldo ou encerramento.
