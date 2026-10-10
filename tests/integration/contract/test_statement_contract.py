from tests.utils import DbUtils, ObjectGenerator, PayloadGenerator, RequestGenerator


STATEMENT_ITEM_KEYS = {
    "transaction_key",
    "operation_key",
    "type",
    "direction",
    "amount",
    "balance_effect",
    "counterparty_account_key",
    "created_at",
}


class TestStatementContract:
    def test_deposit_statement_item_has_exact_credit_semantics(self):
        DbUtils.rollback()
        client, account = ObjectGenerator.create_client_with_account()
        deposit = ObjectGenerator.deposit(account["account_key"], client["client_key"], 12345)

        status, statement = RequestGenerator.GET_transactions(
            account["account_key"], client["client_key"], {"limit": 20, "page": 0}
        )

        assert status == 200
        assert set(statement) == {"data", "limit", "page", "is_last_page"}
        assert statement["limit"] == 20
        assert statement["page"] == 0
        assert statement["is_last_page"] is True
        assert len(statement["data"]) == 1

        item = statement["data"][0]
        assert set(item) == STATEMENT_ITEM_KEYS
        assert item["transaction_key"] == deposit["transaction_key"]
        assert item["operation_key"] == deposit["operation_key"]
        assert item["type"] == "deposit"
        assert item["direction"] == "credit"
        assert item["amount"] == 12345
        assert item["balance_effect"] == 12345
        assert item["counterparty_account_key"] is None

    def test_transfer_fee_is_visible_only_to_origin_and_operation_is_correlated(self):
        DbUtils.rollback()
        owner, origin = ObjectGenerator.create_client_with_account()
        receiver, destination = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin["account_key"], owner["client_key"], 50000)

        payload = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=20000)
        status, transfer = RequestGenerator.POST_transaction(
            origin["account_key"], payload, owner["client_key"]
        )
        assert status == 201

        status, origin_statement = RequestGenerator.GET_transactions(
            origin["account_key"], owner["client_key"], {"limit": 20, "page": 0}
        )
        assert status == 200

        same_operation = [
            item
            for item in origin_statement["data"]
            if item["operation_key"] == transfer["operation_key"]
        ]
        assert len(same_operation) == 2
        assert {item["type"] for item in same_operation} == {"transfer", "fee"}

        transfer_item = next(item for item in same_operation if item["type"] == "transfer")
        fee_item = next(item for item in same_operation if item["type"] == "fee")
        assert transfer_item["direction"] == "debit"
        assert transfer_item["balance_effect"] == -20000
        assert transfer_item["counterparty_account_key"] == destination["account_key"]
        assert fee_item["direction"] == "debit"
        assert fee_item["balance_effect"] == -200
        assert fee_item["counterparty_account_key"] is None

        status, destination_statement = RequestGenerator.GET_transactions(
            destination["account_key"], receiver["client_key"], {"limit": 20, "page": 0}
        )
        assert status == 200
        destination_operation = [
            item
            for item in destination_statement["data"]
            if item["operation_key"] == transfer["operation_key"]
        ]
        assert len(destination_operation) == 1
        assert destination_operation[0]["type"] == "transfer"
        assert destination_operation[0]["direction"] == "credit"
        assert destination_operation[0]["balance_effect"] == 20000
        assert destination_operation[0]["counterparty_account_key"] == origin["account_key"]

    def test_pagination_is_stable_complete_and_without_overlap(self):
        DbUtils.rollback()
        client, account = ObjectGenerator.create_client_with_account()
        created = [
            ObjectGenerator.deposit(account["account_key"], client["client_key"], amount)
            for amount in [100, 200, 300, 400, 500]
        ]

        pages = []
        for page in [0, 1, 2]:
            status, response = RequestGenerator.GET_transactions(
                account["account_key"], client["client_key"], {"limit": 2, "page": page}
            )
            assert status == 200
            pages.append(response)

        assert [len(page["data"]) for page in pages] == [2, 2, 1]
        assert [page["is_last_page"] for page in pages] == [False, False, True]

        transaction_keys = [
            item["transaction_key"]
            for page in pages
            for item in page["data"]
        ]
        assert len(transaction_keys) == 5
        assert len(set(transaction_keys)) == 5
        assert set(transaction_keys) == {item["transaction_key"] for item in created}
        assert transaction_keys == [item["transaction_key"] for item in reversed(created)]

        status, repeated_page_zero = RequestGenerator.GET_transactions(
            account["account_key"], client["client_key"], {"limit": 2, "page": 0}
        )
        assert status == 200
        assert repeated_page_zero == pages[0]

    def test_statement_rejects_unknown_query_parameter(self):
        client, account = ObjectGenerator.create_client_with_account()
        status, response = RequestGenerator.GET_transactions(
            account["account_key"], client["client_key"], {"limit": 20, "page": 0, "sort": "asc"}
        )
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_statement_accepts_limit_boundaries_one_and_one_hundred(self):
        DbUtils.rollback()
        client, account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(account["account_key"], client["client_key"], 100)
        ObjectGenerator.deposit(account["account_key"], client["client_key"], 200)

        status, first = RequestGenerator.GET_transactions(
            account["account_key"], client["client_key"], {"limit": 1, "page": 0}
        )
        assert status == 200
        assert len(first["data"]) == 1
        assert first["is_last_page"] is False

        status, large = RequestGenerator.GET_transactions(
            account["account_key"], client["client_key"], {"limit": 100, "page": 0}
        )
        assert status == 200
        assert len(large["data"]) == 2
        assert large["is_last_page"] is True
