"""Policy documents for knowledge-base ingestion.

These deliberately contain what the structured policy record does **not**: rate
cap exceptions for specific cities, the approval chain for a medical cabin
exception, what to do when a conference has pushed every property above the cap,
why non-refundable is the default. None of that fits a schema, and all of it is
what a traveller actually asks about.

That contrast is the point. Without it, `search_policy_knowledge` would answer the
same questions `get_travel_policy` already answers, and there would be no reason
for the sample to have both a policy API and a knowledge base.

Each document is tagged with its tenant so retrieval can be metadata-filtered —
Globex's policy must never answer an Initech question.
"""

from pathlib import Path

from pydantic import BaseModel

DOCUMENTS_DIR = Path(__file__).parent


class PolicyDocument(BaseModel):
    """A document plus the metadata retrieval filters on."""

    doc_id: str
    tenant_id: str
    title: str
    filename: str
    version: str

    @property
    def path(self) -> Path:
        return DOCUMENTS_DIR / self.filename

    def read(self) -> str:
        return self.path.read_text()

    def s3_key(self) -> str:
        """Tenant-prefixed so the bucket layout mirrors the isolation model."""
        return f"policy/{self.tenant_id}/{self.filename}"

    def metadata_key(self) -> str:
        """Sidecar key. Bedrock looks for `<document key>.metadata.json`, exactly."""
        return f"{self.s3_key()}.metadata.json"

    def kb_metadata(self) -> dict[str, str]:
        """Filterable metadata for retrieval.

        `tenant_id` is the field every retrieval filters on (`$eq`), which is what keeps
        one shared index safe for many tenants.

        **This must be uploaded as a sidecar `.metadata.json` file, not as S3 object
        metadata.** Bedrock ingests metadata only from the sidecar; object metadata is
        silently ignored, so a knowledge base built that way indexes documents with no
        `tenant_id` at all — and a filtered query then returns nothing, which reads like a
        broken filter rather than missing metadata.

        Values stay ASCII-folded. Object metadata *required* it (non-ASCII is rejected
        outright), and while JSON has no such limit, keeping one representation avoids a
        title that differs between the index and everywhere else.
        """
        return {
            "tenant_id": self.tenant_id,
            "doc_id": self.doc_id,
            "title": _ascii(self.title),
            "version": self.version,
        }

    def metadata_sidecar(self) -> str:
        """The sidecar file's contents."""
        import json

        return json.dumps({"metadataAttributes": self.kb_metadata()}, indent=2)


def _ascii(value: str) -> str:
    """Fold typographic characters to ASCII for index metadata.

    Only the metadata copy is folded; the document body keeps its real
    punctuation, and so does `title` everywhere else.
    """
    replacements = {"\u2014": "-", "\u2013": "-", "\u2019": "'", "\u201c": '"', "\u201d": '"'}
    for char, ascii_char in replacements.items():
        value = value.replace(char, ascii_char)
    return value.encode("ascii", "ignore").decode()


DOCUMENTS = [
    PolicyDocument(
        doc_id="pol_globex_2026",
        tenant_id="globex",
        title="Globex Corporation — Corporate Travel Policy 2026",
        filename="globex-travel-policy-2026.md",
        version="2026.1",
    ),
    PolicyDocument(
        doc_id="pol_initech_2026",
        tenant_id="initech",
        title="Initech — Business Travel Policy 2026",
        filename="initech-travel-policy-2026.md",
        version="2026.1",
    ),
]


def documents_for(tenant_id: str) -> list[PolicyDocument]:
    return [doc for doc in DOCUMENTS if doc.tenant_id == tenant_id]


__all__ = ["DOCUMENTS", "DOCUMENTS_DIR", "PolicyDocument", "documents_for"]
