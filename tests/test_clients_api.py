from fastapi.testclient import TestClient

from voice_call_agent.main import app

client = TestClient(app)


def test_admin_page_renders():
    response = client.get("/admin")
    assert response.status_code == 200
    assert "Admin Console" in response.text
    assert "clients-table" in response.text


def test_list_clients_and_stats():
    # 1. List clients
    res = client.get("/api/clients")
    assert res.status_code == 200
    clients = res.json()
    assert isinstance(clients, list)
    assert len(clients) >= 1
    first_client = clients[0]
    assert "name" in first_client
    assert "industry" in first_client

    # 2. Get dashboard statistics
    stats_res = client.get("/api/clients/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "total_clients" in stats
    assert "active_clients" in stats
    assert stats["total_clients"] >= 1


def test_client_crud_lifecycle():
    new_client_payload = {
        "name": "Amaravati Elite Residences",
        "contact_person": "K. Srinivas",
        "email": "srinivas@amaravatielite.in",
        "phone": "+91 98480 55443",
        "industry": "Real Estate",
        "languages": ["Telugu", "English"],
        "virtual_number": "+91 866 244 1122",
        "plan": "Growth",
        "status": "active",
        "monthly_minutes_limit": 2000,
        "webhook_url": "https://amaravatielite.in/crm/leads",
    }

    # 1. Create client
    create_res = client.post("/api/clients", json=new_client_payload)
    assert create_res.status_code == 201
    created = create_res.json()
    client_id = created["id"]
    assert created["name"] == "Amaravati Elite Residences"
    assert created["industry"] == "Real Estate"
    assert created["languages"] == ["Telugu", "English"]

    # 2. Get client by ID
    get_res = client.get(f"/api/clients/{client_id}")
    assert get_res.status_code == 200
    assert get_res.json()["contact_person"] == "K. Srinivas"

    # 3. Update client (PATCH)
    update_res = client.patch(
        f"/api/clients/{client_id}",
        json={"status": "paused", "plan": "Pro", "monthly_minutes_limit": 5000},
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["status"] == "paused"
    assert updated["plan"] == "Pro"
    assert updated["monthly_minutes_limit"] == 5000

    # 4. Search and filter
    search_res = client.get("/api/clients?search=Amaravati")
    assert search_res.status_code == 200
    assert any(c["id"] == client_id for c in search_res.json())

    # 5. Delete client
    del_res = client.delete(f"/api/clients/{client_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # 6. Verify client not found after deletion
    get_after_del = client.get(f"/api/clients/{client_id}")
    assert get_after_del.status_code == 404
