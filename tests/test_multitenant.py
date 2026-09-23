import pytest
from fastapi.testclient import TestClient

from voice_call_agent.agent.prompt_templates import build_business_prompt
from voice_call_agent.core.context import BusinessContext
from voice_call_agent.core.context_loader import resolve_business_context
from voice_call_agent.main import app as fastapi_app

client = TestClient(fastapi_app)


def test_auth_admin_login():
    """Test admin login with JWT token generation."""
    res = client.post(
        "/api/auth/login",
        json={"email": "admin@skvoiceagents.com", "password": "admin123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["token_type"] == "bearer"
    assert data["user_type"] == "admin"

    # Test bad login
    res_bad = client.post(
        "/api/auth/login",
        json={"email": "admin@skvoiceagents.com", "password": "wrongpassword"},
    )
    assert res_bad.status_code == 401


def test_businesses_list_and_filter():
    """Test querying businesses endpoint."""
    res = client.get("/api/businesses")
    assert res.status_code == 200
    businesses = res.json()
    assert isinstance(businesses, list)
    assert len(businesses) >= 1

    first = businesses[0]
    assert "id" in first
    assert "name" in first
    assert "industry" in first
    assert "phone_numbers" in first


def test_knowledge_base_endpoints():
    """Test knowledge base listing and CRUD operations."""
    # List businesses to find a valid business_id
    b_res = client.get("/api/businesses")
    assert b_res.status_code == 200
    businesses = b_res.json()
    business_id = businesses[0]["id"]

    # List knowledge entries for business
    kb_res = client.get(f"/api/businesses/{business_id}/knowledge")
    assert kb_res.status_code == 200
    entries = kb_res.json()
    assert isinstance(entries, list)

    # Add a new FAQ entry
    new_entry = {
        "category": "pricing",
        "question": "What is the starting price?",
        "answer": "Prices start from 1.5 Crores onwards.",
        "priority": 10,
    }
    create_res = client.post(f"/api/businesses/{business_id}/knowledge", json=new_entry)
    assert create_res.status_code == 201
    created_entry = create_res.json()
    entry_id = created_entry["id"]
    assert created_entry["status"] == "created"

    # Clean up entry
    del_res = client.delete(f"/api/businesses/{business_id}/knowledge/{entry_id}")
    assert del_res.status_code == 200


def test_analytics_overview():
    """Test analytics overview metrics."""
    res = client.get("/api/analytics/overview")
    assert res.status_code == 200
    data = res.json()
    assert "total_clients" in data
    assert "total_businesses" in data
    assert "total_calls" in data
    assert "total_leads" in data
    assert "total_appointments" in data
    assert data["total_businesses"] >= 1


def test_prompt_template_builder():
    """Test prompt builder with industry-specific context."""
    ctx = BusinessContext(
        business_id="biz_test_01",
        business_name="Green Meadows Estates",
        client_id="cli_01",
        industry="real_estate",
        agent_name="Pooja",
        greeting_text="Welcome to Green Meadows",
        fallback_message="Could you please repeat?",
        after_hours_message="We are closed",
        languages=("te-IN", "en-IN"),
        voice_map={"te-IN": "kavitha", "en-IN": "ishita"},
        tts_pace=1.0,
        llm_model="gemini-3.5-flash-lite",
        max_output_tokens=80,
        temperature=0.7,
        knowledge=(
            {"category": "projects", "question": "Where is the site?", "answer": "Gachibowli, Hyderabad"},
        ),
        enabled_tools=("qualify_lead", "book_appointment"),
        business_hours=(),
    )

    prompt = build_business_prompt(ctx)
    assert "Green Meadows Estates" in prompt
    assert "Pooja" in prompt
    assert "real estate" in prompt.lower()
    assert "Gachibowli, Hyderabad" in prompt


@pytest.mark.anyio
async def test_resolve_business_context_by_phone():
    """Test resolving business context from Exotel virtual number."""
    # Exotel virtual number assigned to Sri Sai Supermarket & Organics
    ctx = await resolve_business_context("04041892488")
    assert ctx is not None
    assert "Sri Sai Supermarket" in ctx.business_name
    assert ctx.agent_name == "Ananya"
    assert "te-IN" in ctx.languages
