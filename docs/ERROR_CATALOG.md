# Catálogo de erros do domínio bancário

Formato público: `title`, `description`, `translation`, `code`.

| HTTP | Code | Situação |
|---:|---|---|
| 400 | QIT000001 | body/query não respeita JSON Schema |
| 403 | QIT000002 | INTERNAL-TOKEN ausente/incorreto |
| 404 | QIT000404 | rota inexistente |
| 405 | QIT000405 | método HTTP não permitido |
| 404 | QIT002001 | cliente inexistente ou escondido por ownership |
| 422 | QIT002002 | CPF inválido |
| 409 | QIT002003 | CPF já cadastrado |
| 422 | QIT002004 | data de nascimento impossível |
| 422 | QIT002005 | cliente menor de 18 anos |
| 422 | QIT002006 | data de nascimento futura |
| 404 | QIT003001 | conta inexistente ou alheia |
| 409 | QIT003002 | cliente já possui conta no MVP |
| 423 | QIT003003 | conta bloqueada/encerrada não pode operar |
| 409 | QIT003004 | tentativa de encerrar conta com saldo |
| 409 | QIT003005 | tentativa de reabrir conta encerrada |
| 422 | QIT003006 | configuração de limites inconsistente |
| 422 | QIT004001 | saldo insuficiente para valor + tarifa |
| 409 | QIT004002 | transferência para a própria conta |
| 409 | QIT004003 | request_control_key reutilizada com outro pedido |
| 422 | QIT004004 | limite por transferência excedido |
| 422 | QIT004005 | limite diário excedido |
| 409 | QIT004006 | funding_reference já aplicada |
| 401 | QIT005001 | X-CLIENT-KEY ausente em recurso de cliente |

`404` para recurso alheio é deliberado para não confirmar a existência do objeto.

## Política de significado

Um erro previsto não é apenas um número. `code` é a identidade programável; `title`,
`description` e `translation` explicam a falha. Erros de status/limite são regras de negócio,
enquanto corpo malformado continua sendo `QIT000001`.
