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

-- Migration 001: reserves and financial integrity
-- Applies to release/submission v1. Never discard a volume to migrate.
BEGIN;
LOCK TABLE account, bank_transaction, account_status_event, billing_configuration IN ACCESS EXCLUSIVE MODE;
CREATE TABLE IF NOT EXISTS schema_migration (
    version VARCHAR(80) PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_migration WHERE version='001_reserves_and_integrity') THEN
        RAISE EXCEPTION 'Migration already applied; use scripts/migrate.py for an idempotent check';
    END IF;
    IF EXISTS (SELECT lower(request_control_key) FROM bank_transaction WHERE request_control_key IS NOT NULL
               GROUP BY lower(request_control_key) HAVING count(*) > 1)
       OR EXISTS (SELECT lower(external_reference) FROM bank_transaction WHERE external_reference IS NOT NULL
                  GROUP BY lower(external_reference) HAVING count(*) > 1) THEN
        RAISE EXCEPTION 'Legacy UUID duplicates require financial reconciliation before migration';
    END IF;
    IF EXISTS (
        SELECT a.id FROM account a LEFT JOIN bank_transaction t
          ON t.origin_account_id=a.id OR t.destination_account_id=a.id
        GROUP BY a.id HAVING a.balance <> COALESCE(SUM(
            CASE WHEN t.destination_account_id=a.id THEN t.amount ELSE -t.amount END),0)
    ) THEN
        RAISE EXCEPTION 'Legacy balances differ from statement; reconcile before migration';
    END IF;
    IF EXISTS (SELECT 1 FROM account a JOIN account_status s ON s.id=a.status_id
               WHERE s.enumerator='closed' AND a.balance<>0) THEN
        RAISE EXCEPTION 'Legacy closed account holds funds; reconcile before migration';
    END IF;
    IF EXISTS (
        SELECT 1 FROM bank_transaction t JOIN transaction_type ty ON ty.id=t.type_id
         WHERE ty.enumerator IN ('transfer','fee') AND NOT EXISTS (
            SELECT 1 FROM bank_transaction pair JOIN transaction_type pt ON pt.id=pair.type_id
             WHERE pair.operation_key=t.operation_key AND pair.origin_account_id=t.origin_account_id
               AND pt.enumerator=CASE WHEN ty.enumerator='transfer' THEN 'fee' ELSE 'transfer' END)
    ) THEN
        RAISE EXCEPTION 'Legacy transfer/fee pairing is inconsistent; reconcile before migration';
    END IF;
END;
$$;
UPDATE bank_transaction SET request_control_key=lower(request_control_key), external_reference=lower(external_reference);
ALTER TABLE bank_transaction ADD CONSTRAINT financial_keys_canonical CHECK (
    (request_control_key IS NULL OR request_control_key=request_control_key::uuid::text)
    AND (external_reference IS NULL OR external_reference=external_reference::uuid::text)
);

CREATE TABLE piggy_bank (
    id SERIAL PRIMARY KEY,
    piggy_bank_key CHAR(36) NOT NULL UNIQUE,
    account_id INTEGER NOT NULL REFERENCES account(id),
    creation_request_key CHAR(36) NOT NULL UNIQUE CHECK(creation_request_key=creation_request_key::uuid::text),
    creation_fingerprint VARCHAR(64) NOT NULL,
    creation_response JSONB,
    name VARCHAR(80) NOT NULL,
    name_normalized VARCHAR(160) NOT NULL,
    description VARCHAR(255),
    target_amount BIGINT NOT NULL CHECK(target_amount BETWEEN 1 AND 100000000),
    target_date DATE,
    balance BIGINT NOT NULL DEFAULT 0 CHECK(balance>=0),
    status VARCHAR(10) NOT NULL DEFAULT 'active' CHECK(status IN ('active','closed')),
    version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT piggy_bank_unique_name UNIQUE(account_id,name_normalized),
    CONSTRAINT empty_closed_piggy CHECK(status<>'closed' OR balance=0)
);
CREATE INDEX piggy_bank_account_idx ON piggy_bank(account_id,id DESC);
CREATE TABLE piggy_bank_event (
    id BIGSERIAL PRIMARY KEY,
    event_key CHAR(36) NOT NULL UNIQUE,
    piggy_bank_id INTEGER NOT NULL REFERENCES piggy_bank(id),
    type VARCHAR(10) NOT NULL CHECK(type IN ('created','updated','closed')),
    version INTEGER NOT NULL CHECK(version>0),
    changes JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX piggy_bank_event_piggy_idx ON piggy_bank_event(piggy_bank_id,id DESC);
INSERT INTO transaction_type(enumerator) VALUES ('reserve'),('redeem');
ALTER TABLE bank_transaction
    ADD COLUMN piggy_bank_id INTEGER REFERENCES piggy_bank(id),
    ADD COLUMN account_balance_after BIGINT,
    ADD COLUMN piggy_balance_after BIGINT,
    ALTER COLUMN created_at SET DEFAULT clock_timestamp();
CREATE INDEX bank_transaction_piggy_idx ON bank_transaction(piggy_bank_id,id DESC);

CREATE FUNCTION reject_financial_history_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Financial and audit history is immutable' USING ERRCODE='23514';
END;
$$;
CREATE TRIGGER immutable_financial_transaction BEFORE UPDATE OR DELETE ON bank_transaction
FOR EACH ROW EXECUTE FUNCTION reject_financial_history_change();
CREATE TRIGGER immutable_account_event BEFORE UPDATE OR DELETE ON account_status_event
FOR EACH ROW EXECUTE FUNCTION reject_financial_history_change();
CREATE TRIGGER immutable_piggy_event BEFORE UPDATE OR DELETE ON piggy_bank_event
FOR EACH ROW EXECUTE FUNCTION reject_financial_history_change();

CREATE FUNCTION guard_account_identity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_state TEXT; new_state TEXT;
BEGIN
    IF NEW.id<>OLD.id OR NEW.account_key<>OLD.account_key OR NEW.client_id<>OLD.client_id THEN
        RAISE EXCEPTION 'Account ownership and identity are immutable' USING ERRCODE='23514';
    END IF;
    SELECT enumerator INTO old_state FROM account_status WHERE id=OLD.status_id;
    SELECT enumerator INTO new_state FROM account_status WHERE id=NEW.status_id;
    IF old_state='closed' AND new_state<>'closed' THEN
        RAISE EXCEPTION 'Closed account is final' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER account_identity BEFORE UPDATE ON account FOR EACH ROW EXECUTE FUNCTION guard_account_identity();
CREATE FUNCTION guard_piggy_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.id<>OLD.id OR NEW.piggy_bank_key<>OLD.piggy_bank_key OR NEW.account_id<>OLD.account_id
       OR NEW.creation_request_key<>OLD.creation_request_key OR NEW.creation_fingerprint<>OLD.creation_fingerprint
       OR (OLD.creation_response IS NOT NULL AND NEW.creation_response IS DISTINCT FROM OLD.creation_response) THEN
        RAISE EXCEPTION 'Piggy ownership and creation receipt are immutable' USING ERRCODE='23514';
    END IF;
    IF OLD.status='closed' AND NEW.status<>'closed' THEN
        RAISE EXCEPTION 'Closed piggy is final' USING ERRCODE='23514';
    END IF;
    IF ROW(NEW.name,NEW.name_normalized,NEW.description,NEW.target_amount,NEW.target_date,NEW.status)
       IS DISTINCT FROM ROW(OLD.name,OLD.name_normalized,OLD.description,OLD.target_amount,OLD.target_date,OLD.status)
       AND NEW.version<>OLD.version+1 THEN
        RAISE EXCEPTION 'Metadata edits require the next version' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER piggy_identity BEFORE UPDATE ON piggy_bank FOR EACH ROW EXECUTE FUNCTION guard_piggy_identity();

CREATE FUNCTION verify_financial_shape() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE kind TEXT; owner_id INTEGER;
BEGIN
    SELECT enumerator INTO kind FROM transaction_type WHERE id=NEW.type_id;
    IF kind='deposit' THEN
        IF NEW.origin_account_id IS NOT NULL OR NEW.destination_account_id IS NULL OR NEW.piggy_bank_id IS NOT NULL
           OR NEW.request_control_key IS NULL OR NEW.external_reference IS NULL THEN
            RAISE EXCEPTION 'Invalid deposit shape' USING ERRCODE='23514';
        END IF;
    ELSIF kind='transfer' THEN
        IF NEW.origin_account_id IS NULL OR NEW.destination_account_id IS NULL OR NEW.piggy_bank_id IS NOT NULL
           OR NEW.request_control_key IS NULL OR NEW.external_reference IS NOT NULL THEN
            RAISE EXCEPTION 'Invalid transfer shape' USING ERRCODE='23514';
        END IF;
    ELSIF kind='fee' THEN
        IF NEW.origin_account_id IS NULL OR NEW.destination_account_id IS NOT NULL OR NEW.piggy_bank_id IS NOT NULL
           OR NEW.request_control_key IS NOT NULL OR NEW.external_reference IS NOT NULL THEN
            RAISE EXCEPTION 'Invalid fee shape' USING ERRCODE='23514';
        END IF;
    ELSIF kind IN ('reserve','redeem') THEN
        SELECT account_id INTO owner_id FROM piggy_bank WHERE id=NEW.piggy_bank_id;
        IF NEW.piggy_bank_id IS NULL OR NEW.request_control_key IS NULL OR NEW.external_reference IS NOT NULL
           OR NEW.account_balance_after IS NULL OR NEW.account_balance_after<0
           OR NEW.piggy_balance_after IS NULL OR NEW.piggy_balance_after<0
           OR (kind='reserve' AND (NEW.origin_account_id IS DISTINCT FROM owner_id OR NEW.destination_account_id IS NOT NULL))
           OR (kind='redeem' AND (NEW.destination_account_id IS DISTINCT FROM owner_id OR NEW.origin_account_id IS NOT NULL)) THEN
            RAISE EXCEPTION 'Invalid reserve ownership or shape' USING ERRCODE='23514';
        END IF;
    ELSE
        RAISE EXCEPTION 'Unknown financial type' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER financial_shape BEFORE INSERT ON bank_transaction
FOR EACH ROW EXECUTE FUNCTION verify_financial_shape();

CREATE FUNCTION verify_account_ledger(account_id_arg INTEGER) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE actual BIGINT; expected NUMERIC; reserved NUMERIC; state TEXT;
BEGIN
    SELECT a.balance,s.enumerator INTO actual,state FROM account a JOIN account_status s ON s.id=a.status_id
     WHERE a.id=account_id_arg;
    SELECT COALESCE(SUM(CASE WHEN destination_account_id=account_id_arg THEN amount ELSE -amount END),0)
      INTO expected FROM bank_transaction WHERE origin_account_id=account_id_arg OR destination_account_id=account_id_arg;
    SELECT COALESCE(SUM(balance),0) INTO reserved FROM piggy_bank WHERE account_id=account_id_arg;
    IF actual<>expected OR (state='closed' AND actual+reserved<>0) THEN
        RAISE EXCEPTION 'Account balance/state differs from financial history' USING ERRCODE='23514';
    END IF;
    IF (SELECT status_id FROM account WHERE id=account_id_arg) IS DISTINCT FROM
       (SELECT status_id FROM account_status_event WHERE account_id=account_id_arg ORDER BY id DESC LIMIT 1) THEN
        RAISE EXCEPTION 'Account status has no matching audit event' USING ERRCODE='23514';
    END IF;
END;
$$;
CREATE FUNCTION verify_piggy_ledger(piggy_id_arg INTEGER) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE actual BIGINT; expected NUMERIC;
BEGIN
    SELECT balance INTO actual FROM piggy_bank WHERE id=piggy_id_arg;
    SELECT COALESCE(SUM(CASE WHEN ty.enumerator='reserve' THEN t.amount ELSE -t.amount END),0)
      INTO expected FROM bank_transaction t JOIN transaction_type ty ON ty.id=t.type_id WHERE t.piggy_bank_id=piggy_id_arg;
    IF actual<>expected THEN
        RAISE EXCEPTION 'Piggy balance differs from financial history' USING ERRCODE='23514';
    END IF;
    IF (SELECT version FROM piggy_bank WHERE id=piggy_id_arg) IS DISTINCT FROM
       (SELECT version FROM piggy_bank_event WHERE piggy_bank_id=piggy_id_arg ORDER BY id DESC LIMIT 1)
       OR (SELECT creation_response FROM piggy_bank WHERE id=piggy_id_arg) IS NULL THEN
        RAISE EXCEPTION 'Reserve metadata has no audit event or creation receipt' USING ERRCODE='23514';
    END IF;
END;
$$;
CREATE FUNCTION verify_financial_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE kind TEXT; expected NUMERIC; paired INTEGER;
BEGIN
    IF TG_TABLE_NAME='account' THEN
        PERFORM verify_account_ledger(NEW.id);
    ELSIF TG_TABLE_NAME='piggy_bank' THEN
        PERFORM verify_account_ledger(NEW.account_id);
        PERFORM verify_piggy_ledger(NEW.id);
    ELSE
        IF NEW.origin_account_id IS NOT NULL THEN PERFORM verify_account_ledger(NEW.origin_account_id); END IF;
        IF NEW.destination_account_id IS NOT NULL THEN PERFORM verify_account_ledger(NEW.destination_account_id); END IF;
        SELECT enumerator INTO kind FROM transaction_type WHERE id=NEW.type_id;
        IF kind IN ('transfer','fee') THEN
            SELECT count(*) INTO paired FROM bank_transaction t JOIN transaction_type ty ON ty.id=t.type_id
             WHERE t.operation_key=NEW.operation_key AND t.origin_account_id=NEW.origin_account_id
               AND ty.enumerator=CASE WHEN kind='transfer' THEN 'fee' ELSE 'transfer' END;
            IF paired<>1 THEN RAISE EXCEPTION 'Transfer and fee must commit together' USING ERRCODE='23514'; END IF;
        END IF;
        IF NEW.piggy_bank_id IS NOT NULL THEN
            PERFORM verify_piggy_ledger(NEW.piggy_bank_id);
            SELECT COALESCE(SUM(CASE WHEN ty.enumerator='reserve' THEN t.amount ELSE -t.amount END),0)
              INTO expected FROM bank_transaction t JOIN transaction_type ty ON ty.id=t.type_id
             WHERE t.piggy_bank_id=NEW.piggy_bank_id AND t.id<=NEW.id;
            IF expected<>NEW.piggy_balance_after THEN
                RAISE EXCEPTION 'Reserve snapshot does not reconstruct history' USING ERRCODE='23514';
            END IF;
            SELECT COALESCE(SUM(CASE WHEN destination_account_id=COALESCE(NEW.origin_account_id,NEW.destination_account_id)
                 THEN amount ELSE -amount END),0) INTO expected FROM bank_transaction
             WHERE (origin_account_id=COALESCE(NEW.origin_account_id,NEW.destination_account_id)
                OR destination_account_id=COALESCE(NEW.origin_account_id,NEW.destination_account_id)) AND id<=NEW.id;
            IF expected<>NEW.account_balance_after THEN
                RAISE EXCEPTION 'Available snapshot does not reconstruct history' USING ERRCODE='23514';
            END IF;
        END IF;
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER account_ledger_commit AFTER INSERT OR UPDATE ON account
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION verify_financial_commit();
CREATE CONSTRAINT TRIGGER piggy_ledger_commit AFTER INSERT OR UPDATE ON piggy_bank
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION verify_financial_commit();
CREATE CONSTRAINT TRIGGER transaction_ledger_commit AFTER INSERT ON bank_transaction
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION verify_financial_commit();

-- Recheck every legacy account before installing the migration marker.
DO $$ DECLARE item RECORD; BEGIN
    FOR item IN SELECT id FROM account LOOP PERFORM verify_account_ledger(item.id); END LOOP;
END; $$;
INSERT INTO schema_migration(version) VALUES ('001_reserves_and_integrity');
COMMIT;
