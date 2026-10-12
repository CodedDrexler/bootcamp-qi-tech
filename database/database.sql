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
-- Migration 001: apply once to an existing base database.
BEGIN;

CREATE TABLE customer (
	id SERIAL NOT NULL, 
	customer_key VARCHAR(36) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	document_number VARCHAR(14) NOT NULL, 
	birthdate DATE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (customer_key), 
	UNIQUE (email), 
	UNIQUE (document_number)
)

;

CREATE TABLE account (
	id SERIAL NOT NULL, 
	account_key VARCHAR(36) NOT NULL, 
	customer_id INTEGER NOT NULL, 
	balance BIGINT NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (balance BETWEEN 0 AND 9000000000000000), 
	CHECK (status IN ('ACTIVE','CLOSED')), 
	CHECK (status != 'CLOSED' OR balance = 0), 
	UNIQUE (account_key), 
	UNIQUE (customer_id), 
	FOREIGN KEY(customer_id) REFERENCES customer (id)
)

;

CREATE TABLE piggy_bank (
	id SERIAL NOT NULL, 
	piggy_bank_key VARCHAR(36) NOT NULL, 
	account_id INTEGER NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	target_amount BIGINT NOT NULL, 
	balance BIGINT NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (account_id, name), 
	CHECK (balance BETWEEN 0 AND 9000000000000000), 
	CHECK (target_amount BETWEEN 1 AND 9000000000000000), 
	CHECK (status IN ('ACTIVE','CLOSED')), 
	CHECK (status != 'CLOSED' OR balance = 0), 
	UNIQUE (piggy_bank_key), 
	FOREIGN KEY(account_id) REFERENCES account (id)
)

;
CREATE INDEX ix_piggy_bank_account_id ON piggy_bank (account_id);

CREATE TABLE bank_transaction (
	id SERIAL NOT NULL, 
	transaction_key VARCHAR(36) NOT NULL, 
	type VARCHAR(12) NOT NULL, 
	amount BIGINT NOT NULL, 
	fee BIGINT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (type IN ('DEPOSIT','WITHDRAWAL','TRANSFER','SAVE','REDEEM')), 
	CHECK (amount BETWEEN 1 AND 9000000000000000), 
	CHECK (fee >= 0), 
	UNIQUE (transaction_key)
)

;

CREATE TABLE ledger_entry (
	id SERIAL NOT NULL, 
	entry_key VARCHAR(36) NOT NULL, 
	transaction_id INTEGER NOT NULL, 
	account_id INTEGER, 
	piggy_bank_id INTEGER, 
	pocket VARCHAR(10) NOT NULL, 
	type VARCHAR(12) NOT NULL, 
	amount BIGINT NOT NULL, 
	balance_after BIGINT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount != 0), 
	CHECK (pocket IN ('CHECKING','PIGGY','CLEARING','FEES')), 
	CHECK ((pocket = 'CHECKING' AND account_id IS NOT NULL AND piggy_bank_id IS NULL AND balance_after IS NOT NULL) OR (pocket = 'PIGGY' AND account_id IS NOT NULL AND piggy_bank_id IS NOT NULL AND balance_after IS NOT NULL) OR (pocket IN ('CLEARING','FEES') AND account_id IS NULL AND piggy_bank_id IS NULL AND balance_after IS NULL)), 
	CHECK (balance_after IS NULL OR balance_after BETWEEN 0 AND 9000000000000000), 
	UNIQUE (entry_key), 
	FOREIGN KEY(transaction_id) REFERENCES bank_transaction (id), 
	FOREIGN KEY(account_id) REFERENCES account (id), 
	FOREIGN KEY(piggy_bank_id) REFERENCES piggy_bank (id)
)

;
CREATE INDEX ix_ledger_entry_piggy_bank_id ON ledger_entry (piggy_bank_id);
CREATE INDEX ix_ledger_entry_account_id ON ledger_entry (account_id);
CREATE INDEX ix_ledger_entry_transaction_id ON ledger_entry (transaction_id);

CREATE TABLE bank_status_event (
	id SERIAL NOT NULL, 
	account_id INTEGER NOT NULL, 
	piggy_bank_id INTEGER, 
	status VARCHAR(10) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (status IN ('ACTIVE','CLOSED')), 
	FOREIGN KEY(account_id) REFERENCES account (id), 
	FOREIGN KEY(piggy_bank_id) REFERENCES piggy_bank (id)
)

;
CREATE INDEX ix_bank_status_event_account_id ON bank_status_event (account_id);

CREATE TABLE idempotency_record (
	id SERIAL NOT NULL, 
	scope VARCHAR(200) NOT NULL, 
	key VARCHAR(128) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	response JSONB, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_idempotency_scope_key UNIQUE (scope, key)
)

;
-- Deferred checks see all entries in the transaction at COMMIT.
CREATE FUNCTION reject_history_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Bank history is immutable' USING ERRCODE = '23514';
END;
$$;
CREATE TRIGGER immutable_ledger BEFORE UPDATE OR DELETE ON ledger_entry
FOR EACH ROW EXECUTE FUNCTION reject_history_change();
CREATE TRIGGER immutable_transaction BEFORE UPDATE OR DELETE ON bank_transaction
FOR EACH ROW EXECUTE FUNCTION reject_history_change();
CREATE TRIGGER immutable_status_event BEFORE UPDATE OR DELETE ON bank_status_event
FOR EACH ROW EXECUTE FUNCTION reject_history_change();

CREATE FUNCTION verify_balanced_transaction() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    total NUMERIC;
    entries BIGINT;
BEGIN
    SELECT COALESCE(SUM(amount), 0), COUNT(*) INTO total, entries
      FROM ledger_entry WHERE transaction_id = NEW.id;
    IF total <> 0 OR entries < 2 THEN
        RAISE EXCEPTION 'Transaction must have at least two balanced entries' USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER balanced_transaction AFTER INSERT ON bank_transaction
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION verify_balanced_transaction();

CREATE FUNCTION verify_entry_owner() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.piggy_bank_id IS NOT NULL AND NOT EXISTS
       (SELECT 1 FROM piggy_bank WHERE id = NEW.piggy_bank_id AND account_id = NEW.account_id) THEN
        RAISE EXCEPTION 'Piggy bank must belong to the entry account' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER entry_owner BEFORE INSERT ON ledger_entry
FOR EACH ROW EXECUTE FUNCTION verify_entry_owner();

CREATE FUNCTION verify_cached_balance() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    expected NUMERIC;
BEGIN
    IF TG_TABLE_NAME = 'account' THEN
        SELECT COALESCE(SUM(amount), 0) INTO expected FROM ledger_entry
         WHERE account_id = NEW.id AND pocket = 'CHECKING';
    ELSE
        SELECT COALESCE(SUM(amount), 0) INTO expected FROM ledger_entry WHERE piggy_bank_id = NEW.id;
    END IF;
    -- NEW can be an intermediate image when a transfer also charges a fee.
    IF TG_TABLE_NAME = 'account' THEN
        IF expected <> (SELECT balance FROM account WHERE id = NEW.id) THEN
            RAISE EXCEPTION 'Checking balance differs from ledger' USING ERRCODE = '23514';
        END IF;
    ELSE
        IF expected <> (SELECT balance FROM piggy_bank WHERE id = NEW.id) THEN
            RAISE EXCEPTION 'Reserve balance differs from ledger' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER checking_balance AFTER INSERT OR UPDATE ON account
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION verify_cached_balance();
CREATE CONSTRAINT TRIGGER reserve_balance AFTER INSERT OR UPDATE ON piggy_bank
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION verify_cached_balance();

COMMIT;
