from tests.utils import DbUtils, ObjectGenerator, PayloadGenerator, RequestGenerator


class TestStatement:
    def test_empty_statement(self):
        client, account = ObjectGenerator.create_client_with_account()
        status, response = RequestGenerator.GET_transactions(
            account["account_key"], client["client_key"]
        )
        assert status == 200
        assert response["data"] == []
        assert response["page"] == 0
        assert response["limit"] == 20
        assert response["is_last_page"] is True

    def test_statement_explains_balance_and_fee(self):
        DbUtils.rollback()
        origin_client, origin_account = ObjectGenerator.create_client_with_account()
        destination_client, destination_account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin_account["account_key"], origin_client["client_key"], 50000)
        payload = PayloadGenerator.create_transfer_payload(destination_account["account_key"], amount=20000)
        status, transfer = RequestGenerator.POST_transaction(
            origin_account["account_key"], payload, origin_client["client_key"]
        )
        assert status == 201

        status, response = RequestGenerator.GET_transactions(
            origin_account["account_key"], origin_client["client_key"]
        )
        assert status == 200
        effects = [item["balance_effect"] for item in response["data"]]
        assert sum(effects) == 29800
        assert sorted(item["type"] for item in response["data"]) == ["deposit", "fee", "transfer"]

        transfer_rows = [item for item in response["data"] if item["type"] == "transfer"]
        fee_rows = [item for item in response["data"] if item["type"] == "fee"]
        assert transfer_rows[0]["operation_key"] == fee_rows[0]["operation_key"]
        assert transfer_rows[0]["operation_key"] == transfer["operation_key"]

        _, account_response = RequestGenerator.GET_account(
            origin_account["account_key"], origin_client["client_key"]
        )
        assert sum(effects) == account_response["balance"]

    def test_destination_statement_gets_credit_without_fee(self):
        origin_client, origin_account = ObjectGenerator.create_client_with_account()
        destination_client, destination_account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin_account["account_key"], origin_client["client_key"], 50000)
        payload = PayloadGenerator.create_transfer_payload(destination_account["account_key"], amount=20000)
        status, _ = RequestGenerator.POST_transaction(
            origin_account["account_key"], payload, origin_client["client_key"]
        )
        assert status == 201

        status, response = RequestGenerator.GET_transactions(
            destination_account["account_key"], destination_client["client_key"]
        )
        assert status == 200
        assert len(response["data"]) == 1
        assert response["data"][0]["type"] == "transfer"
        assert response["data"][0]["direction"] == "credit"
        assert response["data"][0]["balance_effect"] == 20000
        assert response["data"][0]["counterparty_account_key"] == origin_account["account_key"]

    def test_statement_is_newest_first_and_pages_do_not_overlap(self):
        DbUtils.rollback()
        client, account = ObjectGenerator.create_client_with_account()
        created_keys = []
        for amount in [100, 200, 300, 400, 500]:
            payload = PayloadGenerator.create_deposit_payload(amount=amount)
            status, response = RequestGenerator.POST_transaction(
                account["account_key"], payload, client["client_key"]
            )
            assert status == 201
            created_keys.append(response["transaction_key"])
        created_keys.reverse()

        status, page0 = RequestGenerator.GET_transactions(
            account["account_key"], client["client_key"], {"limit": 2, "page": 0}
        )
        status, page1 = RequestGenerator.GET_transactions(
            account["account_key"], client["client_key"], {"limit": 2, "page": 1}
        )
        status, page2 = RequestGenerator.GET_transactions(
            account["account_key"], client["client_key"], {"limit": 2, "page": 2}
        )

        keys0 = [x["transaction_key"] for x in page0["data"]]
        keys1 = [x["transaction_key"] for x in page1["data"]]
        keys2 = [x["transaction_key"] for x in page2["data"]]
        assert keys0 == created_keys[:2]
        assert keys1 == created_keys[2:4]
        assert keys2 == created_keys[4:]
        assert set(keys0).isdisjoint(keys1)
        assert page0["is_last_page"] is False
        assert page1["is_last_page"] is False
        assert page2["is_last_page"] is True

    def test_statement_rejects_invalid_pagination(self):
        client, account = ObjectGenerator.create_client_with_account()
        for params in [
            {"limit": 0},
            {"limit": 101},
            {"page": -1},
            {"unknown": 1},
        ]:
            status, response = RequestGenerator.GET_transactions(
                account["account_key"], client["client_key"], params
            )
            assert status == 400
            assert response["code"] == "QIT000001"

    def test_statement_requires_identity(self):
        client, account = ObjectGenerator.create_client_with_account()
        status, response = RequestGenerator.GET_transactions(account["account_key"])
        assert status == 401
        assert response["code"] == "QIT005001"

    def test_statement_hides_another_clients_account(self):
        owner, account = ObjectGenerator.create_client_with_account()
        attacker = ObjectGenerator.create_client()
        status, response = RequestGenerator.GET_transactions(
            account["account_key"], attacker["client_key"]
        )
        assert status == 404
        assert response["code"] == "QIT003001"

    def test_statement_of_unknown_account_returns_404(self):
        client = ObjectGenerator.create_client()
        unknown = "00000000-0000-4000-8000-000000000000"
        status, response = RequestGenerator.GET_transactions(unknown, client["client_key"])
        assert status == 404
        assert response["code"] == "QIT003001"
