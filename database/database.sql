CREATE TABLE sample_entity_status(
    id		                        SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(enumerator)
);

INSERT INTO sample_entity_status (enumerator) VALUES
('created'),
('pending'),
('success'),
('failed');

CREATE TABLE sample_entity(
    id                              SERIAL PRIMARY KEY,
    sample_entity_key               CHAR(36) NOT NULL,
    status_id                       INTEGER NOT NULL REFERENCES sample_entity_status(id),
    sample_entity_data              JSONB NOT NULL,
    name                            VARCHAR(255) NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    document_number                 CHAR(14) NOT NULL,
    birthdate                       DATE NOT NULL,
    counter                         INTEGER NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(sample_entity_key),
    UNIQUE(document_number),
    UNIQUE(email)
);

CREATE TABLE sample_entity_status_event(
    id                              SERIAL PRIMARY KEY,
    sample_entity_id                INTEGER NOT NULL REFERENCES sample_entity(id),
    status_id                       INTEGER NOT NULL REFERENCES sample_entity_status(id),
    event_datetime                  TIMESTAMP NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW())
);
-- ============================================================================
-- Domínio bancário do desafio QI Tech
-- ============================================================================
-- Valores monetários usam centavos inteiros (BIGINT). O teto técnico do
-- contrato é R$ 1.000.000,00; limites de risco são menores e vivem na conta.

CREATE TABLE client(
    id                              SERIAL PRIMARY KEY,
    client_key                      CHAR(36) NOT NULL,
    name                            VARCHAR(255) NOT NULL,
    document_number                 CHAR(14) NOT NULL,
    birth_date                      DATE NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(client_key),
    UNIQUE(document_number)
);

CREATE TABLE account_status(
    id                              SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(enumerator)
);

INSERT INTO account_status (enumerator) VALUES
('active'),
('blocked'),
('closed');

CREATE TABLE account(
    id                              SERIAL PRIMARY KEY,
    account_key                     CHAR(36) NOT NULL,
    client_id                       INTEGER NOT NULL REFERENCES client(id),
    status_id                       INTEGER NOT NULL REFERENCES account_status(id),
    balance                         BIGINT NOT NULL DEFAULT 0,
    single_transfer_limit           BIGINT NOT NULL DEFAULT 500000,
    daily_transfer_limit            BIGINT NOT NULL DEFAULT 2000000,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(account_key),
    UNIQUE(client_id),
    CONSTRAINT account_balance_non_negative CHECK (balance >= 0),
    CONSTRAINT account_single_transfer_limit_positive CHECK (single_transfer_limit > 0),
    CONSTRAINT account_daily_transfer_limit_positive CHECK (daily_transfer_limit > 0),
    CONSTRAINT account_daily_limit_not_below_single_limit CHECK (
        daily_transfer_limit >= single_transfer_limit
    )
);

CREATE TABLE account_status_event(
    id                              SERIAL PRIMARY KEY,
    account_id                      INTEGER NOT NULL REFERENCES account(id),
    status_id                       INTEGER NOT NULL REFERENCES account_status(id),
    event_datetime                  TIMESTAMP NOT NULL DEFAULT(NOW()),
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW())
);

CREATE TABLE transaction_type(
    id                              SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(enumerator)
);

INSERT INTO transaction_type (enumerator) VALUES
('deposit'),
('transfer'),
('fee');

CREATE TABLE billing_configuration(
    id                              SERIAL PRIMARY KEY,
    operation_type                  VARCHAR(50) NOT NULL,
    expense_type                    VARCHAR(30) NOT NULL,
    fixed_amount_cents              BIGINT,
    percentage_basis_points         INTEGER,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    updated_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(operation_type),
    CONSTRAINT billing_configuration_expense_type CHECK (
        expense_type IN ('fixed_amount', 'percentage')
    ),
    CONSTRAINT billing_configuration_shape CHECK (
        (expense_type = 'fixed_amount'
            AND fixed_amount_cents IS NOT NULL
            AND fixed_amount_cents > 0
            AND percentage_basis_points IS NULL)
        OR
        (expense_type = 'percentage'
            AND fixed_amount_cents IS NULL
            AND percentage_basis_points IS NOT NULL
            AND percentage_basis_points > 0
            AND percentage_basis_points <= 10000)
    )
);

-- Política comercial do MVP: tarifa fixa de R$ 2,00 por transferência
-- concluída. O operador pode alterar a política interna para valor fixo ou
-- percentual; o cliente final não controla sua própria tarifa.
INSERT INTO billing_configuration (
    operation_type, expense_type, fixed_amount_cents, percentage_basis_points
) VALUES ('transfer', 'fixed_amount', 200, NULL);

CREATE TABLE bank_transaction(
    id                              BIGSERIAL PRIMARY KEY,
    transaction_key                 CHAR(36) NOT NULL,
    operation_key                   CHAR(36) NOT NULL,
    request_control_key             CHAR(36),
    external_reference              CHAR(36),
    type_id                         INTEGER NOT NULL REFERENCES transaction_type(id),
    origin_account_id               INTEGER REFERENCES account(id),
    destination_account_id          INTEGER REFERENCES account(id),
    amount                          BIGINT NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(transaction_key),
    UNIQUE(request_control_key),
    UNIQUE(external_reference),
    CONSTRAINT bank_transaction_operation_type_unique UNIQUE(operation_key, type_id),
    CONSTRAINT bank_transaction_amount_positive CHECK (amount > 0),
    CONSTRAINT bank_transaction_amount_contract_max CHECK (amount <= 100000000),
    CONSTRAINT bank_transaction_has_account CHECK (
        origin_account_id IS NOT NULL OR destination_account_id IS NOT NULL
    ),
    CONSTRAINT bank_transaction_distinct_accounts CHECK (
        origin_account_id IS NULL
        OR destination_account_id IS NULL
        OR origin_account_id <> destination_account_id
    )
);

CREATE INDEX bank_transaction_origin_created_idx
    ON bank_transaction(origin_account_id, created_at DESC, id DESC);
CREATE INDEX bank_transaction_destination_created_idx
    ON bank_transaction(destination_account_id, created_at DESC, id DESC);
CREATE INDEX bank_transaction_operation_key_idx
    ON bank_transaction(operation_key);
