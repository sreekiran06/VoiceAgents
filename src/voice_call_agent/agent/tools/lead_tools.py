from typing import Any

from voice_call_agent.agent.tools.registry import ToolRegistry


def qualify_lead(
    requirement: str,
    budget: str | None = None,
    location: str | None = None,
    timeline: str | None = None,
    name: str | None = None,
    phone: str | None = None,
) -> dict[str, Any]:
    """Capture and qualify a prospective customer lead."""
    return {
        "lead_captured": True,
        "requirement": requirement,
        "budget": budget,
        "location": location,
        "timeline": timeline,
        "name": name,
        "phone": phone,
        "message": "Lead details saved successfully.",
    }


def book_appointment(
    customer_name: str,
    phone: str,
    appointment_type: str,
    date: str,
    time: str,
) -> dict[str, Any]:
    """Schedule an appointment, consultation, or site visit."""
    return {
        "booking_confirmed": True,
        "customer_name": customer_name,
        "phone": phone,
        "appointment_type": appointment_type,
        "date": date,
        "time": time,
        "confirmation_code": f"SK-{abs(hash(customer_name + date + time)) % 10000:04d}",
    }


def transfer_to_human(department: str = "support", reason: str = "") -> dict[str, Any]:
    """Request a transfer to a human specialist."""
    return {
        "transfer_requested": True,
        "department": department,
        "reason": reason,
        "message": f"Connecting caller to {department} team.",
    }


def register_default_tools(registry: ToolRegistry) -> None:
    """Register default telecalling business tools into the registry."""
    registry.register(
        name="qualify_lead",
        description="Save lead requirements such as budget, location, requirement, timeline, and contact info.",
        parameters={
            "type": "object",
            "properties": {
                "requirement": {"type": "string", "description": "What caller is looking for (e.g., 2BHK flat, dental checkup)"},
                "budget": {"type": "string", "description": "Budget range or price constraint"},
                "location": {"type": "string", "description": "Preferred area or city"},
                "timeline": {"type": "string", "description": "Expected timeframe (e.g. immediate, within 1 month)"},
                "name": {"type": "string", "description": "Customer name"},
                "phone": {"type": "string", "description": "Customer phone number"},
            },
            "required": ["requirement"],
        },
        handler=qualify_lead,
    )

    registry.register(
        name="book_appointment",
        description="Book a site visit, consultation, demo, or appointment.",
        parameters={
            "type": "object",
            "properties": {
                "customer_name": {"type": "string", "description": "Name of the customer"},
                "phone": {"type": "string", "description": "Customer contact number"},
                "appointment_type": {"type": "string", "description": "Type of booking: site visit, clinic visit, demo"},
                "date": {"type": "string", "description": "Date of appointment (e.g. 2026-09-10 or tomorrow)"},
                "time": {"type": "string", "description": "Time of appointment (e.g. 11:00 AM)"},
            },
            "required": ["customer_name", "phone", "appointment_type", "date", "time"],
        },
        handler=book_appointment,
    )

    registry.register(
        name="transfer_to_human",
        description="Transfer call to a human executive when customer requests human help or query cannot be answered.",
        parameters={
            "type": "object",
            "properties": {
                "department": {"type": "string", "description": "Target department, e.g. sales, support, counsellor"},
                "reason": {"type": "string", "description": "Reason for transfer"},
            },
            "required": ["department"],
        },
        handler=transfer_to_human,
    )
