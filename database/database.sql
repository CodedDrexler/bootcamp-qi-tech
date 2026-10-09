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
-- O projeto-base continua intacto acima. As tabelas abaixo implementam o
-- cadastro de clientes, contas, movimentações, tarifa e extrato.
-- Dinheiro é sempre armazenado em centavos inteiros (BIGINT).

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

CREATE TABLE account(
    id                              SERIAL PRIMARY KEY,
    account_key                     CHAR(36) NOT NULL,
    client_id                       INTEGER NOT NULL REFERENCES client(id),
    balance                         BIGINT NOT NULL DEFAULT 0,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(account_key),
    CONSTRAINT account_balance_non_negative CHECK (balance >= 0)
);

CREATE INDEX account_client_id_idx ON account(client_id);

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

CREATE TABLE bank_transaction(
    id                              BIGSERIAL PRIMARY KEY,
    transaction_key                 CHAR(36) NOT NULL,
    operation_key                   CHAR(36) NOT NULL,
    request_control_key             CHAR(36),
    type_id                         INTEGER NOT NULL REFERENCES transaction_type(id),
    origin_account_id               INTEGER REFERENCES account(id),
    destination_account_id          INTEGER REFERENCES account(id),
    amount                          BIGINT NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(transaction_key),
    UNIQUE(request_control_key),
    CONSTRAINT bank_transaction_amount_positive CHECK (amount > 0),
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
