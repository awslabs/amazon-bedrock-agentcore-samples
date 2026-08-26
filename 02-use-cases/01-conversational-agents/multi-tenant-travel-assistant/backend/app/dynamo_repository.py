"""DynamoDB implementation of the repository protocol.

A mechanical translation of the in-memory store, which is why the seam was worth
having: routers and services are unchanged, and the test suite still runs with no
AWS at all.

Two details carry real weight:

**Keys are `TENANT#<id>` / `<TYPE>#<id>`.** The partition key is the isolation
boundary — a `dynamodb:LeadingKeys` condition on the assumed data role makes IAM
refuse a cross-tenant query before it reaches data. Every method here takes a
tenant precisely so that shape is impossible to bypass by accident.

**Decimals, not floats.** DynamoDB stores numbers as `Decimal`, and money must
survive the round trip exactly. Pydantic already coerces to a quantised
`Decimal`, so the conversion happens at the boundary rather than in each model.
"""

import json
import time
from datetime import datetime
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

from .models import (
    HeldOffer,
    OfferStatus,
    Reservation,
    TenantConfig,
    TravelerProfile,
    TravelPolicy,
    Trip,
    tenant_pk,
)
from .repository import OfferConflictError, TenantNotFoundError

# **Long enough for one conversation, short enough that a forgotten scenario cannot linger.**
# An eval task is one turn; a person walking the demo takes minutes. Nothing here should outlive
# the session that armed it, and DynamoDB TTL guarantees that without a cleanup step.
SCENARIO_TTL_SECONDS = 1800


def _to_dynamo(model: Any) -> dict:
    """Model to item, via JSON so nested types collapse to primitives.

    Floats are rejected by DynamoDB, and `json.loads(parse_float=Decimal)` keeps
    money exact without walking the model tree by hand.
    """
    return json.loads(model.model_dump_json(), parse_float=Decimal)


def _from_dynamo(item: dict) -> dict:
    """Item to plain dict, dropping the key attributes the models don't carry."""
    return {k: _plain(v) for k, v in item.items() if k not in ("pk", "sk", "ttl")}


def _plain(value: Any) -> Any:
    """Decimals back to str so Pydantic parses them exactly."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


class DynamoRepository:
    """Tenant-scoped reads and writes over the six tables."""

    def __init__(self, table_prefix: str, dynamodb_resource: Any | None = None):
        resource = dynamodb_resource or boto3.resource("dynamodb")
        self._t = {
            name: resource.Table(f"{table_prefix}-{name}")
            for name in ("travelers", "trips", "bookings", "offers", "policies", "tenant-config")
        }

    # --- writes ---

    def put_tenant_config(self, config: TenantConfig) -> None:
        self._t["tenant-config"].put_item(
            Item={"pk": tenant_pk(config.tenant_id), "sk": "CONFIG", **_to_dynamo(config)}
        )

    def put_policy(self, policy: TravelPolicy) -> None:
        self._t["policies"].put_item(
            Item={
                "pk": tenant_pk(policy.tenant_id),
                "sk": f"POLICY#{policy.topic}",
                **_to_dynamo(policy),
            }
        )

    def put_traveler(self, traveler: TravelerProfile) -> None:
        self._t["travelers"].put_item(
            Item={
                "pk": tenant_pk(traveler.tenant_id),
                "sk": f"TRAVELER#{traveler.traveler_id}",
                **_to_dynamo(traveler),
            }
        )

    def put_trip(self, trip: Trip) -> None:
        self._t["trips"].put_item(
            Item={
                "pk": tenant_pk(trip.tenant_id),
                "sk": f"TRIP#{trip.trip_id}",
                "traveler_id": trip.traveler_id,
                **_to_dynamo(trip),
            }
        )

    def put_offer(self, offer: HeldOffer) -> None:
        # TTL a little past expiry: the row must outlive the offer so a confirm
        # attempt on a lapsed hold still finds it and can say "expired" rather
        # than "never existed".
        self._t["offers"].put_item(
            Item={
                "pk": tenant_pk(offer.tenant_id),
                "sk": f"OFFER#{offer.offer_id}",
                "ttl": int(offer.expires_at.timestamp()) + 3600,
                **_to_dynamo(offer),
            }
        )

    def put_reservation(self, reservation: Reservation) -> None:
        self._t["bookings"].put_item(
            Item={
                "pk": tenant_pk(reservation.tenant_id),
                "sk": f"BOOKING#{reservation.booking_ref}",
                "traveler_id": reservation.traveler_id,
                **_to_dynamo(reservation),
            }
        )

    def consume_offer(self, offer: HeldOffer, reservation: Reservation) -> None:
        """Consume the offer and create its reservation, atomically, or do neither.

        **The unconditional `put_item` this replaces could book twice.** `confirm` reads the offer,
        checks it is held, re-prices, then writes. Two concurrent requests — a double-click, or an
        HTTP retry after a timeout — both read `held`, both pass the check, and both write. The
        second overwrote the first's offer row and added a second reservation. In a real system that
        is a second charge, which makes the sample's central claim (money moves only after an
        explicit request) untrue.

        **Two conditions, and each closes a different hole.** `status = held` on the offer means
        exactly one writer can transition it, so the loser is told rather than served.
        `attribute_not_exists(sk)` on the reservation means a booking cannot be created twice even
        if the offer row were somehow reset — and because `booking_ref` is derived from the offer id
        (`bkg_<offer suffix>`), a retry of the same confirmation targets the same item rather than
        inventing a second one. The offer id is already the idempotency key; nothing new had to be
        invented for it.

        **One transaction rather than two conditional writes**, because the failure between them is
        the worst outcome available: an offer marked consumed with no reservation is a traveller
        charged for a booking that does not exist, and it cannot be retried — the offer is spent.
        `TransactWriteItems` makes the pair all-or-nothing.

        Uses the resource's underlying client because transactions are a client-level operation;
        `Table` has no equivalent.
        """
        table_arn_names = (self._t["offers"].name, self._t["bookings"].name)
        try:
            self._t["offers"].meta.client.transact_write_items(
                TransactItems=[
                    {
                        "Update": {
                            "TableName": table_arn_names[0],
                            "Key": {
                                "pk": tenant_pk(offer.tenant_id),
                                "sk": f"OFFER#{offer.offer_id}",
                            },
                            "UpdateExpression": "SET #status = :consumed",
                            "ConditionExpression": "#status = :held",
                            "ExpressionAttributeNames": {"#status": "status"},
                            "ExpressionAttributeValues": {
                                ":consumed": OfferStatus.CONSUMED.value,
                                ":held": OfferStatus.HELD.value,
                            },
                        }
                    },
                    {
                        "Put": {
                            "TableName": table_arn_names[1],
                            "Item": {
                                "pk": tenant_pk(reservation.tenant_id),
                                "sk": f"BOOKING#{reservation.booking_ref}",
                                "traveler_id": reservation.traveler_id,
                                **_to_dynamo(reservation),
                            },
                            "ConditionExpression": "attribute_not_exists(sk)",
                        }
                    },
                ]
            )
        except ClientError as error:
            # `TransactionCanceledException` is the only failure that means "a condition said no";
            # anything else is a genuine storage fault and must not be reported as a lost race.
            if error.response["Error"]["Code"] == "TransactionCanceledException":
                raise OfferConflictError(offer.offer_id) from None
            raise

    def put_scenarios(self, tenant_id: str, session_id: str, scenarios: set[str]) -> None:
        """Arm simulated conditions for one conversation.

        **In the offers table because that is already the ephemeral, TTL'd store**, and a scenario
        has an offer's lifetime characteristics: it belongs to one session, it must expire on its
        own, and nothing should read it an hour later. A new table would be new infrastructure for
        a row that lives for minutes.

        **Keyed on the session, never on the tenant.** A tenant-wide switch would put the deployed
        demo into "every search times out" for whoever arrived next, and leave it there. Session
        scope also makes the session id the capability: an eval run arms its own conversation and
        can affect no other.
        """
        self._t["offers"].put_item(
            Item={
                "pk": tenant_pk(tenant_id),
                "sk": f"SCENARIO#{session_id}",
                "ttl": int(time.time()) + SCENARIO_TTL_SECONDS,
                "scenarios": sorted(scenarios),
            }
        )

    def active_scenarios(self, tenant_id: str, session_id: str | None) -> set[str]:
        if not session_id:
            return set()
        item = self._get("offers", tenant_id, f"SCENARIO#{session_id}")
        if not item:
            return set()
        return {str(name) for name in item.get("scenarios") or []}

    # --- reads ---

    def tenant_config(self, tenant_id: str) -> TenantConfig:
        item = self._get("tenant-config", tenant_id, "CONFIG")
        if item is None:
            raise TenantNotFoundError(tenant_id)
        return TenantConfig(**item)

    def policy(self, tenant_id: str, topic: str) -> TravelPolicy | None:
        item = self._get("policies", tenant_id, f"POLICY#{topic}")
        return TravelPolicy(**item) if item else None

    def policies(self, tenant_id: str) -> list[TravelPolicy]:
        return [TravelPolicy(**i) for i in self._query("policies", tenant_id, "POLICY#")]

    def traveler(self, tenant_id: str, traveler_id: str) -> TravelerProfile | None:
        item = self._get("travelers", tenant_id, f"TRAVELER#{traveler_id}")
        return TravelerProfile(**item) if item else None

    def travelers(self, tenant_id: str) -> list[TravelerProfile]:
        return [TravelerProfile(**i) for i in self._query("travelers", tenant_id, "TRAVELER#")]

    def trips(self, tenant_id: str, traveler_id: str | None = None) -> list[Trip]:
        items = self._query("trips", tenant_id, "TRIP#")
        trips = [Trip(**i) for i in items]
        if traveler_id is not None:
            trips = [t for t in trips if t.traveler_id == traveler_id]
        return sorted(trips, key=lambda t: t.starts_on)

    def trip(self, tenant_id: str, trip_id: str) -> Trip | None:
        item = self._get("trips", tenant_id, f"TRIP#{trip_id}")
        return Trip(**item) if item else None

    def offer(self, tenant_id: str, offer_id: str) -> HeldOffer | None:
        item = self._get("offers", tenant_id, f"OFFER#{offer_id}")
        return HeldOffer(**item) if item else None

    def reservation(self, tenant_id: str, booking_ref: str) -> Reservation | None:
        item = self._get("bookings", tenant_id, f"BOOKING#{booking_ref}")
        return Reservation(**item) if item else None

    def reservations(self, tenant_id: str, traveler_id: str | None = None) -> list[Reservation]:
        items = self._query("bookings", tenant_id, "BOOKING#")
        found = [Reservation(**i) for i in items]
        if traveler_id is not None:
            found = [r for r in found if r.traveler_id == traveler_id]
        return found

    def expire_offers(self, now: datetime) -> int:
        """DynamoDB TTL handles this; nothing to sweep."""
        return 0

    # --- helpers ---

    def _get(self, table: str, tenant_id: str, sk: str) -> dict | None:
        """Read one item, **strongly consistent**.

        `get_item` is eventually consistent by default, and this application reads its own writes
        within seconds: the booking path holds an offer and then confirms it, which in a live run
        produced a `404` on an offer that existed, was `held`, and belonged to the right traveller.
        Eleven seconds after the write, against a ten-minute TTL — so it read as an expired or
        foreign
        handle, which is the most misleading way this could fail.

        The cost is double the read capacity and slightly higher latency. Worth it here: every read
        through this repository feeds an authorization or a booking decision, and a stale miss
        becomes
        a refusal the traveller cannot act on.
        """
        response = self._t[table].get_item(
            Key={"pk": tenant_pk(tenant_id), "sk": sk}, ConsistentRead=True
        )
        item = response.get("Item")
        return _from_dynamo(item) if item else None

    def _query(self, table: str, tenant_id: str, sk_prefix: str) -> list[dict]:
        """Query one tenant partition, **strongly consistent** and paginated.

        Two ways this silently under-reports, and a trip count that is one short produces a wrong
        entitlement verdict rather than an error:

        - a partial page, hence the pagination loop below;
        - an eventually-consistent read that has not caught up with a recent write. Same reasoning
        as
          `_get` — a booking made moments ago must appear in the history the next decision reads.
        """
        from boto3.dynamodb.conditions import Key

        condition = Key("pk").eq(tenant_pk(tenant_id)) & Key("sk").begins_with(sk_prefix)
        items: list[dict] = []
        kwargs: dict[str, Any] = {"KeyConditionExpression": condition, "ConsistentRead": True}

        while True:
            response = self._t[table].query(**kwargs)
            items.extend(_from_dynamo(i) for i in response.get("Items", []))
            token = response.get("LastEvaluatedKey")
            if not token:
                return items
            kwargs["ExclusiveStartKey"] = token
