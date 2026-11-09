def test_create_order_returns_201_and_the_order(client, order_payload):
    resp = client.post("/orders", json=order_payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] >= 1
    assert body["status"] == "created"
    assert body["customer"] == "ada"


def test_get_order_round_trip(client, order_payload):
    created = client.post("/orders", json=order_payload).json()
    resp = client.get(f"/orders/{created['id']}")
    assert resp.status_code == 200
    assert resp.json() == created


def test_unknown_order_uses_house_error_format(client):
    resp = client.get("/orders/999")
    assert resp.status_code == 404
    assert resp.json() == {"error": "order_not_found"}


def test_invalid_order_is_rejected(client, order_payload):
    resp = client.post("/orders", json={**order_payload, "quantity": 0})
    assert resp.status_code == 422
    assert resp.json() == {"error": "invalid_request"}


def test_list_orders_is_newest_first(client, order_payload):
    for item in ("a", "b", "c"):
        client.post("/orders", json={**order_payload, "item": item})
    items = [o["item"] for o in client.get("/orders", params={"limit": 2}).json()]
    assert items == ["c", "b"]
