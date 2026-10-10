from concurrent.futures import ThreadPoolExecutor

from tests.utils import DbUtils, ObjectGenerator, PayloadGenerator, RequestGenerator


class TestConcurrency:
    def test_opposite_direction_transfers_finish_without_deadlock(self):
        DbUtils.rollback()
        client_a, account_a = ObjectGenerator.create_client_with_account()
        client_b, account_b = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(account_a["account_key"], client_a["client_key"], 50000)
        ObjectGenerator.deposit(account_b["account_key"], client_b["client_key"], 50000)

        payload_ab = PayloadGenerator.create_transfer_payload(account_b["account_key"], amount=10000)
        payload_ba = PayloadGenerator.create_transfer_payload(account_a["account_key"], amount=10000)

        def transfer_a_to_b():
            return RequestGenerator.POST_transaction(
                account_a["account_key"], payload_ab, client_a["client_key"]
            )

        def transfer_b_to_a():
            return RequestGenerator.POST_transaction(
                account_b["account_key"], payload_ba, client_b["client_key"]
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_ab = executor.submit(transfer_a_to_b)
            future_ba = executor.submit(transfer_b_to_a)
            results = [future_ab.result(timeout=15), future_ba.result(timeout=15)]

        assert sorted(status for status, _ in results) == [201, 201]

        _, final_a = RequestGenerator.GET_account(account_a["account_key"], client_a["client_key"])
        _, final_b = RequestGenerator.GET_account(account_b["account_key"], client_b["client_key"])
        assert final_a["balance"] == 49800
        assert final_b["balance"] == 49800

    def test_many_concurrent_spends_never_overdraw_origin(self):
        DbUtils.rollback()
        origin_client, origin_account = ObjectGenerator.create_client_with_account()
        destinations = [ObjectGenerator.create_client_with_account()[1] for _ in range(8)]
        ObjectGenerator.deposit(origin_account["account_key"], origin_client["client_key"], 5200)

        payloads = [
            PayloadGenerator.create_transfer_payload(destination["account_key"], amount=1000)
            for destination in destinations
        ]

        def send(payload):
            return RequestGenerator.POST_transaction(
                origin_account["account_key"], payload, origin_client["client_key"]
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(send, payloads))

        statuses = [status for status, _ in results]
        assert statuses.count(201) == 4
        assert statuses.count(422) == 4

        _, origin = RequestGenerator.GET_account(
            origin_account["account_key"], origin_client["client_key"]
        )
        assert origin["balance"] == 400

        _, statement = RequestGenerator.GET_transactions(
            origin_account["account_key"], origin_client["client_key"]
        )
        transfer_rows = [item for item in statement["data"] if item["type"] == "transfer"]
        fee_rows = [item for item in statement["data"] if item["type"] == "fee"]
        assert len(transfer_rows) == 4
        assert len(fee_rows) == 4
        assert sum(item["balance_effect"] for item in statement["data"]) == 400

    def test_concurrent_replay_storm_executes_financial_effect_once(self):
        DbUtils.rollback()
        origin_client, origin_account = ObjectGenerator.create_client_with_account()
        destination_client, destination_account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin_account["account_key"], origin_client["client_key"], 30000)
        payload = PayloadGenerator.create_transfer_payload(destination_account["account_key"], amount=10000)

        def send(_):
            return RequestGenerator.POST_transaction(
                origin_account["account_key"], payload, origin_client["client_key"]
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(send, range(8)))

        assert all(status == 201 for status, _ in results)
        first_body = results[0][1]
        assert all(body == first_body for _status, body in results)

        _, origin = RequestGenerator.GET_account(
            origin_account["account_key"], origin_client["client_key"]
        )
        _, destination = RequestGenerator.GET_account(
            destination_account["account_key"], destination_client["client_key"]
        )
        assert origin["balance"] == 19800
        assert destination["balance"] == 10000

        _, statement = RequestGenerator.GET_transactions(
            origin_account["account_key"], origin_client["client_key"]
        )
        assert len([row for row in statement["data"] if row["type"] == "transfer"]) == 1
        assert len([row for row in statement["data"] if row["type"] == "fee"]) == 1
