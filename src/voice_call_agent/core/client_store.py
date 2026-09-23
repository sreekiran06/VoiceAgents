import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from voice_call_agent.models.client import CallRecord, Client, ClientCreate, ClientUpdate, LeadRecord

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
            agent_name="Kiran",
            greeting_text="నమస్కారం! శ్రీ కృష్ణ ఇన్ఫ్రా కి స్వాగతం. మీకు ఎలా సహాయం చేయగలను?",
            leads=[
                LeadRecord(
                    id="lead-hyd-101",
                    name="Srinivas Rao",
                    phone="+91 98480 99887",
                    email="srinivas.rao@gmail.com",
                    requirement="3BHK East-Facing Luxury Apartment with 2 Car Parkings",
                    budget="1.45 - 1.60 Cr",
                    location="Gachibowli Financial District, Hyderabad",
                    timeline="Immediate (within 30 days)",
                    status="converted",
                    created_at="Today, 02:46 PM",
                    notes="Site visit confirmed for Saturday 11:00 AM. Interested in 12th floor unit.",
                    call_id="call-101",
                ),
                LeadRecord(
                    id="lead-hyd-102",
                    name="Kavitha Sharma",
                    phone="+91 97000 44332",
                    email="kavitha.s@outlook.com",
                    requirement="Commercial Plot or Villa Plot for investment",
                    budget="80 Lakhs - 1.1 Cr",
                    location="Kokapet SEZ Road",
                    timeline="Next 2-3 months",
                    status="qualified",
                    created_at="Today, 11:16 AM",
                    notes="Requested brochure & HMDA layout approval copy over WhatsApp.",
                    call_id="call-102",
                ),
                LeadRecord(
                    id="lead-hyd-103",
                    name="Rajesh Varma",
                    phone="+91 98855 22110",
                    requirement="2.5 or 3BHK Gated Community flat near Metro station",
                    budget="1.20 Cr",
                    location="Miyapur / Hitec City corridor",
                    timeline="Within 60 days",
                    status="contacted",
                    created_at="Yesterday, 04:20 PM",
                    notes="Follow-up call scheduled for Monday 5 PM.",
                ),
                LeadRecord(
                    id="lead-hyd-104",
                    name="Anand Kumar",
                    phone="+91 94411 77889",
                    requirement="Duplex Penthouse 4BHK with terrace garden",
                    budget="2.5 Cr+",
                    location="Gachibowli",
                    timeline="Exploring options",
                    status="new",
                    created_at="2026-09-20 06:10 PM",
                    notes="Inbound web callback lead.",
                ),
            ],
            recent_calls=[
                CallRecord(
                    call_id="call-101",
                    caller_phone="+91 98480 99887",
                    call_time="Today, 02:45 PM",
                    duration_seconds=124,
                    language_detected="Telugu",
                    status="completed",
                    sentiment="Positive",
                    recording_url="/api/calls/call-101/audio",
                    summary="Customer Srinivas Rao inquired about 3BHK flats in Gachibowli under 1.5 Cr. AI Agent Kiran qualified budget, confirmed 2 car parking availability, and scheduled site visit for Saturday 11:00 AM.",
                    transcript=[
                        {"speaker": "Caller", "role": "user", "text": "నమస్తే అండి, గచ్చిబౌలిలో మీ ప్రాజెక్ట్‌లో 3BHK ఫ్లాట్స్ ఉన్నాయా?", "time": "00:03"},
                        {"speaker": "AI Agent (Kiran)", "role": "assistant", "text": "నమస్తే శ్రీనివాస్ గారు! అవునండి, గచ్చిబౌలి ఫైనాన్షియల్ డిస్ట్రిక్ట్‌లో మా లగ్జరీ 3BHK ప్రాజెక్ట్ 'కృష్ణ హైట్స్' అందుబాటులో ఉంది. మీ బడ్జెట్ ఎంతవరకు అనుకుంటున్నారు?", "time": "00:09"},
                        {"speaker": "Caller", "role": "user", "text": "సుమారు 1.4 నుండి 1.5 కోట్ల వరకు. ఈస్ట్ ఫేసింగ్ కావాలి, కార్ పార్కింగ్ 2 ఉంటాయా?", "time": "00:22"},
                        {"speaker": "AI Agent (Kiran)", "role": "assistant", "text": "ఖచ్చితంగా అండి! 1850 చదరపు అడుగుల ఈస్ట్ ఫేసింగ్ యూనిట్స్ అందుబాటులో ఉన్నాయి మరియు డబుల్ కార్ పార్కింగ్ సౌకర్యం కూడా ఉంది.", "time": "00:32"},
                        {"speaker": "Caller", "role": "user", "text": "చాలా బాగుంది. డైరెక్ట్ గా వచ్చి చూడవచ్చా?", "time": "00:46"},
                        {"speaker": "AI Agent (Kiran)", "role": "assistant", "text": "తప్పకుండా అండి! ఈ శనివారం ఉదయం 11:00 గంటలకు మా సైట్ ఎగ్జిక్యూటివ్‌తో అపాయింట్‌మెంట్ కన్ఫర్మ్ చేయమంటారా?", "time": "00:54"},
                        {"speaker": "Caller", "role": "user", "text": "సరే, 11 గంటలకు కన్ఫర్మ్ చేయండి. నా నంబర్‌కి లొకేషన్ పంపించండి.", "time": "01:06"},
                        {"speaker": "AI Agent (Kiran)", "role": "assistant", "text": "ఖచ్చితంగా అండి! మీ అపాయింట్‌మెంట్ కన్ఫర్మ్ అయింది మరియు లొకేషన్ వివరాలు మీ మొబైల్‌కు ఎస్సెమ్మెస్ చేసాము. ధన్యవాదాలు!", "time": "01:14"},
                    ],
                ),
                CallRecord(
                    call_id="call-102",
                    caller_phone="+91 97000 44332",
                    call_time="Today, 11:15 AM",
                    duration_seconds=78,
                    language_detected="English",
                    status="completed",
                    sentiment="Inquiry",
                    recording_url="/api/calls/call-102/audio",
                    summary="Kavitha Sharma inquired about Kokapet commercial villa plots. Agent shared price per sq yard and sent HMDA approval catalog.",
                    transcript=[
                        {"speaker": "Caller", "role": "user", "text": "Hi, I saw your billboard for commercial plots in Kokapet. Are they HMDA approved?", "time": "00:04"},
                        {"speaker": "AI Agent (Kiran)", "role": "assistant", "text": "Hello! Yes, all our Kokapet plots are 100% HMDA approved and RERA registered with clear titles.", "time": "00:11"},
                        {"speaker": "Caller", "role": "user", "text": "What is the price per square yard?", "time": "00:20"},
                        {"speaker": "AI Agent (Kiran)", "role": "assistant", "text": "Plots start at Rs 65,000 per sq yard for 200 to 500 sq yards plots. I can share the complete brochure and layout map to your WhatsApp right now.", "time": "00:28"},
                        {"speaker": "Caller", "role": "user", "text": "Yes please send it to this number.", "time": "00:42"},
                        {"speaker": "AI Agent (Kiran)", "role": "assistant", "text": "Sent! Our sales advisor will follow up with you shortly. Have a wonderful day!", "time": "00:48"},
                    ],
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
            agent_name="Priya",
            greeting_text="నమస్కారం! Apollo Clinic కి కాల్ చేసినందుకు ధన్యవాదాలు. మీకు ఎలా సహాయం చేయగలను?",
            leads=[
                LeadRecord(
                    id="lead-vja-201",
                    name="Nageswara Rao",
                    phone="+91 94900 11223",
                    requirement="Cardiology Consultation with Senior Specialist",
                    budget="Consultation Fee: ₹800",
                    location="Governorpet, Vijayawada",
                    timeline="Tomorrow 05:30 PM",
                    status="converted",
                    created_at="Today, 01:21 PM",
                    notes="Patient has mild chest tightness and previous ECG reports.",
                    call_id="call-201",
                ),
                LeadRecord(
                    id="lead-vja-202",
                    name="Lakshmi Devi",
                    phone="+91 98481 33445",
                    requirement="Orthopedic Knee pain checkup",
                    budget="Consultation Fee: ₹600",
                    location="MG Road, Vijayawada",
                    timeline="This Friday morning",
                    status="qualified",
                    created_at="Yesterday, 10:45 AM",
                    notes="Wants appointment with Dr. Chaitanya.",
                ),
            ],
            recent_calls=[
                CallRecord(
                    call_id="call-201",
                    caller_phone="+91 94900 11223",
                    call_time="Today, 01:20 PM",
                    duration_seconds=95,
                    language_detected="Telugu",
                    status="completed",
                    sentiment="Urgent",
                    recording_url="/api/calls/call-201/audio",
                    summary="Booked cardiologist consultation with Dr. S. Murthy for tomorrow at 5:30 PM for patient Nageswara Rao.",
                    transcript=[
                        {"speaker": "Caller", "role": "user", "text": "నమస్తే అండి, రేపు కార్డియాలజిస్ట్ డాక్టర్ గారు ఉంటారా? అపాయింట్‌మెంట్ కావాలి.", "time": "00:03"},
                        {"speaker": "AI Agent (Priya)", "role": "assistant", "text": "నమస్తే అండి! అవును, మా సీనియర్ కార్డియాలజిస్ట్ డాక్టర్ ఎస్. మూర్తి గారు రేపు సాయంత్రం 4:30 నుండి 8:00 వరకు అందుబాటులో ఉంటారు.", "time": "00:10"},
                        {"speaker": "Caller", "role": "user", "text": "సాయంత్రం 5:30 సమయం కుదురుతుందా? పేషెంట్ పేరు నాగేశ్వరరావు.", "time": "00:24"},
                        {"speaker": "AI Agent (Priya)", "role": "assistant", "text": "తప్పకుండా అండి! రేపు సాయంత్రం 5:30 గంటలకు డాక్టర్ మూర్తి గారితో అపాయింట్‌మెంట్ కన్ఫర్మ్ చేసాము. కన్ఫర్మేషన్ కోడ్: APL-582.", "time": "00:35"},
                    ],
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
            agent_name="Ravi",
            greeting_text="Hello! Welcome to Narayana Academy. How can I assist you with admissions?",
            leads=[
                LeadRecord(
                    id="lead-vzg-301",
                    name="Suresh Babu (Parent)",
                    phone="+91 98850 11992",
                    requirement="Class 11 (Intermediate 1st Year) MPC IIT-JEE Integrated Batch",
                    budget="Scholarship Test registered",
                    location="Dwaraka Nagar, Visakhapatnam",
                    timeline="Academic Year 2026-27",
                    status="new",
                    created_at="Today, 10:15 AM",
                    notes="Student scored 96% in 10th pre-boards. Registered for NST exam on Sunday.",
                )
            ],
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
            agent_name="Arvind",
            greeting_text="Hello! UrbanFix Premium Services here. How can I help you today?",
            leads=[
                LeadRecord(
                    id="lead-blr-401",
                    name="Amitabh Sen",
                    phone="+91 98110 33445",
                    requirement="Voltas Inverter Split AC Deep Jet Cleaning & Gas Leak Repair",
                    budget="Estimated: ₹1,499",
                    location="Koramangala 4th Block, Bangalore",
                    timeline="Tomorrow 10:00 AM slot",
                    status="converted",
                    created_at="Today, 03:11 PM",
                    notes="Technician assigned: Ramesh K. Slot confirmed.",
                    call_id="call-401",
                )
            ],
            recent_calls=[
                CallRecord(
                    call_id="call-401",
                    caller_phone="+91 98110 33445",
                    call_time="Today, 03:10 PM",
                    duration_seconds=110,
                    language_detected="Hindi",
                    status="completed",
                    sentiment="Positive",
                    recording_url="/api/calls/call-401/audio",
                    summary="Air conditioner deep repair service requested for Koramangala tomorrow 10 AM. Booked technician slot.",
                    transcript=[
                        {"speaker": "Caller", "role": "user", "text": "नमस्ते, मुझे कल सुबह कोरामंगला में एसी सर्विसिंग के लिए टेक्नीशियन चाहिए।", "time": "00:04"},
                        {"speaker": "AI Agent (Arvind)", "role": "assistant", "text": "नमस्ते सर! UrbanFix में आपका स्वागत है। कल सुबह 10:00 बजे का स्लॉट उपलब्ध है। क्या आपका स्प्लिट एसी है या विंडो?", "time": "00:12"},
                        {"speaker": "Caller", "role": "user", "text": "1.5 टन का स्प्लिट एसी है, कूलिंग कम हो रही है।", "time": "00:24"},
                        {"speaker": "AI Agent (Arvind)", "role": "assistant", "text": "जी बिल्कुल! हमने कल सुबह 10:00 बजे के लिए जेट सर्विस और गैस चेकअप स्लॉट बुक कर दिया है।", "time": "00:36"},
                    ],
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
            leads=[],
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

    async def update_lead_status(
        self, client_id: str, lead_id: str, new_status: str
    ) -> LeadRecord | None:
        async with self._lock:
            client = self._clients.get(client_id)
            if not client:
                return None
            for lead in client.leads:
                if lead.id == lead_id:
                    lead.status = new_status  # type: ignore[assignment]
                    self._save_sync()
                    return lead
            return None

    async def add_lead(self, client_id: str, lead: LeadRecord) -> LeadRecord | None:
        async with self._lock:
            client = self._clients.get(client_id)
            if not client:
                return None
            client.leads.insert(0, lead)
            client.leads_captured = len(client.leads)
            self._save_sync()
            return lead

    async def get_stats(self) -> dict[str, Any]:
        async with self._lock:
            clients = list(self._clients.values())
            total_clients = len(clients)
            active_clients = sum(1 for c in clients if c.status == "active")
            total_minutes_used = sum(c.minutes_used for c in clients)
            total_leads = sum(len(c.leads) if c.leads else c.leads_captured for c in clients)
            total_appointments = sum(c.appointments_booked for c in clients)

            return {
                "total_clients": total_clients,
                "active_clients": active_clients,
                "total_minutes_used": total_minutes_used,
                "total_leads_captured": total_leads,
                "total_appointments_booked": total_appointments,
            }


client_store = ClientStore()
