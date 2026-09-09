import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from voice_call_agent.models.client import CallRecord, Client, ClientCreate, ClientUpdate

logger = logging.getLogger(__name__)


def _get_initial_seed_clients() -> list[Client]:
    return [
        Client(
            id="cli-hyd-001",
            name="Sri Krishna Infra & Developers",
            contact_person="Ramesh Reddy",
            email="ramesh@srikrishnainfra.in",
            phone="+91 98490 12345",
            industry="Real Estate",
            languages=["Telugu", "English"],
            virtual_number="+91 40 4821 5566",
            plan="Growth",
            status="active",
            monthly_minutes_limit=2500,
            minutes_used=742,
            leads_captured=48,
            appointments_booked=21,
            created_at="2026-08-15 10:30",
            webhook_url="https://crm.srikrishnainfra.in/api/webhooks/voice",
            recent_calls=[
                CallRecord(
                    call_id="call-101",
                    caller_phone="+91 98480 99887",
                    call_time="Today, 02:45 PM",
                    duration_seconds=124,
                    language_detected="Telugu",
                    status="completed",
                    summary="Customer inquired about 3BHK flats in Gachibowli under 1.5 Cr. Booked site visit for Saturday 11 AM.",
                    transcript=[
                        {"speaker": "Caller", "text": "నమస్తే అండి, గచ్చిబౌలిలో 3BHK ఫ్లాట్స్ ఉన్నాయా?"},
                        {"speaker": "AI Agent", "text": "నమస్తే! అవునండి, గచ్చిబౌలిలో మా లగ్జరీ 3BHK ప్రాజెక్ట్ అందుబాటులో ఉంది. మీ బడ్జెట్ ఎంతవరకు అనుకుంటున్నారు?"},
                        {"speaker": "Caller", "text": "సుమారు 1.5 కోట్ల వరకు."},
                        {"speaker": "AI Agent", "text": "ఖచ్చితంగా సరిపోతుందండి. శనివారం ఉదయం 11 గంటలకు సైట్ విజిట్ షెడ్యూల్ చేయమంటారా?"},
                    ],
                ),
                CallRecord(
                    call_id="call-102",
                    caller_phone="+91 97000 44332",
                    call_time="Today, 11:15 AM",
                    duration_seconds=78,
                    language_detected="English",
                    status="completed",
                    summary="Asked for brochure and pricing sheet of Kokapet commercial plots.",
                ),
            ],
        ),
        Client(
            id="cli-vja-002",
            name="Apollo Multispeciality Clinic",
            contact_person="Dr. Sunita Rao",
            email="appointments@apolloclinicvja.com",
            phone="+91 94401 55667",
            industry="Clinics & Healthcare",
            languages=["Telugu", "Hindi", "English"],
            virtual_number="+91 866 254 9988",
            plan="Growth",
            status="active",
            monthly_minutes_limit=1500,
            minutes_used=520,
            leads_captured=82,
            appointments_booked=67,
            created_at="2026-08-20 14:15",
            webhook_url="https://api.apolloclinicvja.com/webhooks/calls",
            recent_calls=[
                CallRecord(
                    call_id="call-201",
                    caller_phone="+91 94900 11223",
                    call_time="Today, 01:20 PM",
                    duration_seconds=95,
                    language_detected="Telugu",
                    status="completed",
                    summary="Booked cardiologist consultation with Dr. S. Murthy for tomorrow at 5:30 PM.",
                )
            ],
        ),
        Client(
            id="cli-vzg-003",
            name="Narayana IIT & NEET Academy",
            contact_person="P. Venkatesh",
            email="admissions@narayanavzg.edu.in",
            phone="+91 98850 77889",
            industry="Coaching & EdTech",
            languages=["Telugu", "English"],
            virtual_number="+91 891 278 3344",
            plan="Starter",
            status="active",
            monthly_minutes_limit=1000,
            minutes_used=310,
            leads_captured=35,
            appointments_booked=14,
            created_at="2026-09-01 09:00",
            recent_calls=[],
        ),
        Client(
            id="cli-blr-004",
            name="UrbanFix Premium Home Services",
            contact_person="Arvind Sharma",
            email="ops@urbanfix.in",
            phone="+91 99800 22334",
            industry="Local Services",
            languages=["Hindi", "English"],
            virtual_number="+91 80 4912 7700",
            plan="Pro",
            status="active",
            monthly_minutes_limit=5000,
            minutes_used=1840,
            leads_captured=145,
            appointments_booked=110,
            created_at="2026-07-10 16:45",
            webhook_url="https://urbanfix.in/api/v1/voice-leads",
            recent_calls=[
                CallRecord(
                    call_id="call-401",
                    caller_phone="+91 98110 33445",
                    call_time="Today, 03:10 PM",
                    duration_seconds=110,
                    language_detected="Hindi",
                    status="completed",
                    summary="Air conditioner deep repair service requested for Koramangala tomorrow 10 AM.",
                )
            ],
        ),
        Client(
            id="cli-hyd-005",
            name="Vedic Solar Energy Solutions",
            contact_person="Sanjay Varma",
            email="contact@vedicsolar.co.in",
            phone="+91 96180 88990",
            industry="Local Services",
            languages=["Telugu", "English"],
            virtual_number="+91 40 6718 2211",
            plan="Starter",
            status="onboarding",
            monthly_minutes_limit=1000,
            minutes_used=24,
            leads_captured=3,
            appointments_booked=1,
            created_at="2026-09-06 11:20",
            recent_calls=[],
        ),
    ]


class ClientStore:
    """Store for managing business client profiles with file persistence."""

    def __init__(self, persistence_file: Path | None = None) -> None:
        self._lock = asyncio.Lock()
        self._persistence_file = persistence_file or Path(__file__).parent.parent.parent / "clients_data.json"
        self._clients: dict[str, Client] = {}
        self._load()

    def _load(self) -> None:
        if self._persistence_file.exists():
            try:
                with open(self._persistence_file, encoding="utf-8") as f:
                    data = json.load(f)
                self._clients = {item["id"]: Client(**item) for item in data}
                return
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to load clients persistence file: %s", exc)

        # Use seed clients
        seed = _get_initial_seed_clients()
        self._clients = {c.id: c for c in seed}
        self._save_sync()

    def _save_sync(self) -> None:
        try:
            data = [c.model_dump() for c in self._clients.values()]
            with open(self._persistence_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to save clients persistence file: %s", exc)

    async def list_clients(
        self,
        search: str | None = None,
        industry: str | None = None,
        status: str | None = None,
    ) -> list[Client]:
        async with self._lock:
            clients = list(self._clients.values())

            if industry and industry != "All":
                clients = [c for c in clients if c.industry.lower() == industry.lower()]

            if status and status != "All":
                clients = [c for c in clients if c.status.lower() == status.lower()]

            if search:
                term = search.lower().strip()
                clients = [
                    c
                    for c in clients
                    if term in c.name.lower()
                    or term in c.contact_person.lower()
                    or term in c.email.lower()
                    or term in c.phone.lower()
                    or term in c.virtual_number.lower()
                ]

            return sorted(clients, key=lambda c: c.created_at, reverse=True)

    async def get_client(self, client_id: str) -> Client | None:
        async with self._lock:
            return self._clients.get(client_id)

    async def create_client(self, data: ClientCreate) -> Client:
        async with self._lock:
            client_id = f"cli-{uuid.uuid4().hex[:8]}"
            client = Client(id=client_id, **data.model_dump())
            self._clients[client_id] = client
            self._save_sync()
            return client

    async def update_client(self, client_id: str, updates: ClientUpdate) -> Client | None:
        async with self._lock:
            client = self._clients.get(client_id)
            if not client:
                return None

            update_data = updates.model_dump(exclude_unset=True)
            for field, val in update_data.items():
                if val is not None:
                    setattr(client, field, val)

            self._save_sync()
            return client

    async def delete_client(self, client_id: str) -> bool:
        async with self._lock:
            if client_id in self._clients:
                del self._clients[client_id]
                self._save_sync()
                return True
            return False

    async def get_stats(self) -> dict[str, Any]:
        async with self._lock:
            clients = list(self._clients.values())
            total_clients = len(clients)
            active_clients = sum(1 for c in clients if c.status == "active")
            total_minutes_used = sum(c.minutes_used for c in clients)
            total_leads = sum(c.leads_captured for c in clients)
            total_appointments = sum(c.appointments_booked for c in clients)

            return {
                "total_clients": total_clients,
                "active_clients": active_clients,
                "total_minutes_used": total_minutes_used,
                "total_leads_captured": total_leads,
                "total_appointments_booked": total_appointments,
            }


client_store = ClientStore()
