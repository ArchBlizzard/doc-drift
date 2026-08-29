"""Run ledger (T018): append-only JSONL, fingerprinted resume (FR-008).

Line 1 is a RunLedgerHeader; every further line is a LedgerEntry. Resume is
the DEFAULT: a claim is settled iff an entry exists whose claim key
(sha256 of quoted_span + type) matches AND the header's data+card fingerprints
match the current case. `--fresh` deletes the file instead.

The ledger is one artifact serving three deliverables: evidence trail,
re-run cache, and (with messages.jsonl) the published trajectory.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from docdrift.schemas import Claim, LedgerEntry, RunLedgerHeader


def fingerprint_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint_text(text: str) -> str:
    return fingerprint_bytes(text.encode("utf-8"))


def claim_key(claim: Claim) -> str:
    return hashlib.sha256(f"{claim.quoted_span}|{claim.type.value}".encode()).hexdigest()


class Ledger:
    def __init__(self, path: Path, header: RunLedgerHeader):
        self.path = path
        self.header = header

    @classmethod
    def open(cls, path: Path, *, case_id: str, data_fingerprint: str,
             card_fingerprint: str, sdk_version: str, started: str,
             fresh: bool = False) -> "Ledger":
        header = RunLedgerHeader(case_id=case_id, data_fingerprint=data_fingerprint,
                                 card_fingerprint=card_fingerprint,
                                 sdk_version=sdk_version, started=started)
        if fresh and path.exists():
            path.unlink()
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(header.model_dump_json() + "\n", encoding="utf-8")
        return cls(path, header)

    def settled(self) -> dict[str, LedgerEntry]:
        """Entries reusable for THIS case (fingerprints must match)."""
        lines = self.path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return {}
        stored = RunLedgerHeader.model_validate_json(lines[0])
        if (stored.data_fingerprint != self.header.data_fingerprint
                or stored.card_fingerprint != self.header.card_fingerprint):
            return {}
        out: dict[str, LedgerEntry] = {}
        for line in lines[1:]:
            entry = LedgerEntry.model_validate_json(line)
            out[claim_key(entry.claim)] = entry
        return out

    def append(self, entry: LedgerEntry) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(entry.model_dump_json(exclude_none=True) + "\n")

    def entries(self) -> list[LedgerEntry]:
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [LedgerEntry.model_validate_json(line) for line in lines[1:]]

    def stats(self) -> dict[str, int]:
        entries = self.entries()
        return {
            "entries": len(entries),
            "tokens_in": sum(e.tokens_in for e in entries),
            "tokens_out": sum(e.tokens_out for e in entries),
            "vacuous_rejections": sum(
                sum(m.outcome.value == "vacuous" for m in e.mutant_results) for e in entries),
        }
