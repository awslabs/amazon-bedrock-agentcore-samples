// AUTO-GENERATED from shared/cards.py by scripts/generate_card_types.py
// Do not edit by hand — run the script instead.
//
// Cards cross a language boundary: Python tools emit them, this file types the renderer. The
// generated `CardType` union is what makes the renderer's switch exhaustive, so adding a card type
// in Python produces a *compile error* here rather than a silently unrendered tile.

export type CardType =
  | "booking_confirmed"
  | "booking_summary"
  | "cancellation"
  | "citation"
  | "entry_requirements"
  | "escalation"
  | "flight_option"
  | "hotel_option"
  | "place"
  | "policy_verdict"
  | "profile"
  | "route"
  | "trip";

/** Closed registry: the frontend must refuse an action outside this union. */
export type ActionId =
  | "confirm_booking"
  | "confirm_cancel"
  | "decline_booking"
  | "get_directions"
  | "keep_booking"
  | "select_flight"
  | "select_hotel"
  | "view_details"
  | "view_fare_rules"
  | "view_travel_policy"
  | "view_trip";

export interface CardAction<P = Record<string, unknown>> {
  id: ActionId;
  label: string;
  payload: P;
}

export interface Card<D = Record<string, unknown>> {
  card_type: CardType;
  /** Stable, referenceable — the model may cite it as `[card:<id>]`. */
  id: string;
  data: D;
  actions?: CardAction[];
}

/** Required `data` keys per card type — a minimum, not a closed schema. */
export const REQUIRED_DATA: Record<CardType, readonly string[]> = {
  flight_option: [
    "arrive_airport",
    "arrive_time",
    "cabin",
    "carrier",
    "depart_airport",
    "depart_time",
    "duration_min",
    "flight_number",
    "in_policy",
    "price",
    "stops",
  ],
  hotel_option: [
    "address",
    "amenities",
    "in_policy",
    "name",
    "nightly_rate",
    "star_rating",
    "total",
  ],
  trip: [
    "destination",
    "end_date",
    "segments",
    "start_date",
    "status",
    "trip_id",
  ],
  profile: ["home_airport", "loyalty", "passport_country", "traveler_name"],
  policy_verdict: ["eligible", "reason_code", "request_label", "rule_quote"],
  booking_summary: ["items", "mode", "payment_label", "policy_status", "total"],
  booking_confirmed: ["confirmation_number", "issued_at", "items", "total"],
  cancellation: ["booking_label", "stage", "terms"],
  entry_requirements: [
    "destination_country",
    "disclaimer",
    "passport_country",
    "requirement",
  ],
  place: ["address", "categories", "distance_m", "name"],
  route: ["destination", "distance_km", "duration_min", "mode", "origin"],
  escalation: ["context_summary_line", "reason_label", "status"],
  citation: ["doc_id", "label"],
} as const;

/** Which actions each card type may carry. */
export const ALLOWED_ACTIONS: Record<CardType, readonly ActionId[]> = {
  flight_option: ["select_flight", "view_fare_rules"],
  hotel_option: ["select_hotel", "view_details"],
  trip: ["view_trip"],
  profile: [],
  policy_verdict: ["view_travel_policy"],
  booking_summary: ["confirm_booking", "decline_booking"],
  booking_confirmed: [],
  cancellation: ["confirm_cancel", "keep_booking"],
  entry_requirements: [],
  place: ["get_directions"],
  route: [],
  escalation: [],
  citation: [],
} as const;
