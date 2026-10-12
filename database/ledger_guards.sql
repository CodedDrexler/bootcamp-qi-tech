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
