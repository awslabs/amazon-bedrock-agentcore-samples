"""Tool schemas for the booking family — the single source of truth.

**Three tools, one lifecycle.** `prepare_booking` holds a priced option, `confirm_booking` executes
it, `cancel_reservation` undoes it. They are one family because the `booking_ref` handle only makes
sense across all three, and splitting them across directories would let the lifecycle drift.

**Every input is an identifier the server re-derives from, never a value.** No prices, no
descriptions, no traveller ids. A client-held reference is forgeable, so the server re-prices and
re-validates ownership on every step — which is why `confirm_booking` takes *only* the handle.

**No `enum`.** Closed sets ride in descriptions; the tool enforces them.
"""

from typing import Any

PREPARE_BOOKING = "prepare_booking"
CONFIRM_BOOKING = "confirm_booking"
CANCEL_RESERVATION = "cancel_reservation"

# Closed set, enforced in code.
KINDS = ("air", "hotel")

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": PREPARE_BOOKING,
        "label": "Preparing your booking",
        "description": (
            "Price and hold one option the traveller has chosen, and return a summary for them to "
            "review before anything is booked. Takes the option id from a search result card — "
            "never a price or a description, because the server re-derives those. Always call this "
            "before confirming: it is what produces the booking reference confirmation needs, and "
            "it is where the traveller sees the total and the payment method."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "option_id": {
                    "type": "string",
                    "description": (
                        "The id of the chosen option, exactly as it appeared in a search result. "
                        "Do not invent or modify it."
                    ),
                },
                "kind": {
                    "type": "string",
                    "description": "What is being booked: 'air' or 'hotel'.",
                },
                "destination": {
                    "type": "string",
                    "description": (
                        "The destination from the search that produced this option — needed to "
                        "regenerate and re-price it."
                    ),
                },
                "origin": {
                    "type": "string",
                    "description": "For 'air': the origin from the original search.",
                },
                "depart_on": {
                    "type": "string",
                    "description": (
                        "For 'air': the departure date from the original search, "
                        "YYYY-MM-DD. **Copy it "
                        "exactly, including the year** — the option id encodes it, so a different "
                        "year names a different search and the hold is refused."
                    ),
                },
                "check_in": {
                    "type": "string",
                    "description": (
                        "For 'hotel': the check-in date from the original search, "
                        "YYYY-MM-DD. **Copy it "
                        "exactly, including the year** — the option id encodes these dates, so a "
                        "different year names a different search and the hold is refused."
                    ),
                },
                "check_out": {
                    "type": "string",
                    "description": (
                        "For 'hotel': the check-out date from the original search, YYYY-MM-DD."
                    ),
                },
                "traveler_name": {
                    "type": "string",
                    "description": (
                        "Only when booking for someone else — the name as the user said it. Omit "
                        "for the caller."
                    ),
                },
            },
            "required": ["option_id", "kind", "destination"],
        },
    },
    {
        "name": CONFIRM_BOOKING,
        "label": "Confirming your booking",
        "description": (
            "Book a prepared offer. **Only call this after the traveller has explicitly "
            "confirmed in their own words** — never on your own initiative, never as a follow-up "
            "to a search, "
            "and never to 'save time'. Takes only the booking reference from prepare_booking; the "
            "price is re-derived server-side, so if the fare moved this refuses rather than "
            "charging a different amount. Some companies do not permit booking in chat at all; the "
            "prepared summary says which."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "booking_ref": {
                    "type": "string",
                    "description": (
                        "The reference returned by prepare_booking, copied exactly. It always "
                        "begins with 'off_' followed by hex — for example 'off_294eae67b1'. Never "
                        "invent one, never reuse an old one, and never construct it from the "
                        "flight"
                        "details. If you do not have a reference from prepare_booking in this "
                        "conversation, call prepare_booking first."
                    ),
                }
            },
            "required": ["booking_ref"],
        },
    },
    {
        "name": CANCEL_RESERVATION,
        "label": "Checking cancellation terms",
        "description": (
            "Cancel a booking — in two steps. Called without `confirm`, it returns the penalties "
            "and deadlines and cancels **nothing**. Call it again with confirm set to true only "
            "after the traveller has seen those terms and agreed to them. 'Cancel my hotel' is not "
            "agreement to a penalty they have not been shown."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "booking_ref": {
                    "type": "string",
                    "description": "The reference of the reservation to cancel.",
                },
                "confirm": {
                    "type": "boolean",
                    "description": (
                        "Set true only after the traveller has seen the cancellation terms and "
                        "agreed. Omit or set false to retrieve the terms."
                    ),
                },
            },
            "required": ["booking_ref"],
        },
    },
]
