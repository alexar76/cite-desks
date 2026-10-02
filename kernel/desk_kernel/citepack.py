from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from .claim import ClaimClass
from .delta import compare_briefs


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str).encode("utf-8")


def _ascii(text: Any) -> str:
    return (
        str(text or "")
        .replace("→", "->")
        .replace("—", "-")
        .replace("–", "-")
        .replace("·", "|")
        .replace("≥", ">=")
        .encode("ascii", "replace")
        .decode("ascii")
    )


def _pack_time(brief: dict[str, Any]) -> datetime:
    raw = brief.get("generated_at")
    if raw:
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_pdf_class(claim: ClaimClass) -> type[FPDF]:
    header = claim.cite_header
    footer = claim.cite_footer

    class CitePDF(FPDF):
        def header(self) -> None:
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(90, 70, 55)
            self.set_x(self.l_margin)
            self.multi_cell(0, 4, _ascii(header), wrapmode="CHAR")
            self.set_draw_color(180, 150, 120)
            y = self.get_y() + 1
            self.line(16, y, 194, y)
            self.set_xy(self.l_margin, y + 4)

        def footer(self) -> None:
            self.set_y(-14)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(110, 95, 80)
            self.cell(
                0,
                8,
                f"Page {self.page_no()}  |  {_ascii(footer)}",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
                align="C",
            )

    return CitePDF


def _p(pdf: FPDF, text: str, *, size: int = 10, bold: bool = False, h: int = 5) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B" if bold else "", size)
    pdf.set_text_color(26, 18, 14)
    pdf.multi_cell(0, h, _ascii(text), wrapmode="CHAR")


def _items(brief: dict[str, Any]) -> list[dict[str, Any]]:
    return list(
        brief.get("items")
        or brief.get("hotspots")
        or brief.get("warnings")
        or brief.get("vessels")
        or []
    )


def render_cover_pdf(claim: ClaimClass, brief: dict[str, Any], delta: dict[str, Any]) -> bytes:
    when = _pack_time(brief)
    pdf_cls = _make_pdf_class(claim)
    pdf = pdf_cls(format="A4")
    pdf.set_creation_date(when)
    pdf.set_title(_ascii((brief.get("watch") or {}).get("name") or claim.product_name))
    pdf.set_author(claim.cite_author)
    pdf.set_creator(claim.cite_creator)
    pdf.set_subject(_ascii(claim.cite_subject))
    pdf.set_margins(16, 18, 16)
    pdf.set_auto_page_break(auto=True, margin=18)
    watch = brief.get("watch") or {}
    bbox = watch.get("bbox") or {}
    point = watch.get("point") or {}
    receipt = brief.get("receipt") or {}
    source_proofs = brief.get("source_proofs") or []
    pdf.add_page()
    _p(pdf, watch.get("name") or "Unnamed watch", size=20, bold=True, h=9)
    _p(pdf, f"{brief.get('generated_at')}  |  {brief.get('id')}  |  run {brief.get('run_id')}", size=10)
    if bbox:
        _p(
            pdf,
            f"bbox {bbox.get('west')} / {bbox.get('south')}  ->  {bbox.get('east')} / {bbox.get('north')}",
            size=10,
        )
    if point:
        _p(pdf, f"point {point.get('lat')}, {point.get('lon')}", size=10)
    pdf.ln(2)
    _p(
        pdf,
        f"{brief.get('evidence_status')}  |  {brief.get(claim.count_field, brief.get('live_count'))} LIVE",
        size=12,
        bold=True,
    )
    _p(pdf, delta.get("summary") or "", size=11)
    pdf.ln(1)
    _p(pdf, brief.get("summary") or "", size=10)
    pdf.ln(2)
    _p(pdf, "Badges", size=10, bold=True)
    _p(pdf, "  |  ".join(brief.get("badges") or list(claim.badges)), size=10)
    if receipt:
        _p(pdf, "Receipt", size=10, bold=True)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Courier", "", 8)
        pdf.multi_cell(
            0,
            4,
            _ascii(
                f"status={receipt.get('signature_status')}  "
                f"{claim.verified_key}={receipt.get(claim.verified_key)}\n"
                f"digest={receipt.get('digest')}\n"
                f"capability={receipt.get('capability_id')}"
            ),
            wrapmode="CHAR",
        )
    if source_proofs:
        verified = sum(1 for proof in source_proofs if proof.get("attestation_verified"))
        _p(pdf, "Source proofs", size=10, bold=True)
        _p(
            pdf,
            f"{len(source_proofs)} preserved; {verified} device attestations verify for payload integrity; identities are not desk-pinned.",
            size=8,
        )
    pdf.ln(2)
    _p(pdf, brief.get("legal_strip") or claim.legal_strip, size=9)
    pdf.add_page()
    _p(pdf, claim.items_heading, size=13, bold=True)
    pdf.set_font("Courier", "", 8)
    for item in _items(brief)[:40]:
        pdf.set_x(pdf.l_margin)
        line = (
            f"{item.get('id') or '-'}  {item.get('lat')}  {item.get('lon')}  "
            f"{item.get('kind') or item.get('headline') or item.get('label') or ''}"
        )
        pdf.multi_cell(0, 4, _ascii(line), wrapmode="CHAR")
    return bytes(pdf.output())


def _readme(claim: ClaimClass, brief: dict[str, Any]) -> str:
    return (
        f"{claim.readme_title}\n"
        "===================\n\n"
        "This zip is the object you hand to intake. It is a monitoring aid.\n"
        f"{claim.legal_strip}\n\n"
        f"Brief: {brief.get('id')}\n"
        f"Run:   {brief.get('run_id')}\n"
        f"Watch: {(brief.get('watch') or {}).get('name')}\n"
        f"When:  {brief.get('generated_at')}\n\n"
        "Quote the brief id, generated_at, evidence_status, and root receipt digest when present.\n"
        "For multi-source briefs, quote source device ids; source-proofs preserves each reading, device attestation, and Hub receipt.\n"
        "Use files under raw/ — do not re-draw geometry this desk did not store.\n"
        "Verify SHA256SUMS against every file except SHA256SUMS itself.\n"
    )


def build_cite_pack(
    *,
    claim: ClaimClass,
    brief: dict[str, Any],
    raw: dict[str, Any] | None = None,
) -> bytes:
    delta = brief.get("delta") or compare_briefs(claim, brief, None)
    files: dict[str, bytes] = {
        "00-README.txt": _readme(claim, brief).encode("utf-8"),
        "01-cover.pdf": render_cover_pdf(claim, brief, delta),
        "02-brief.json": _json_bytes(brief),
        "03-delta.json": _json_bytes(delta),
        "04-receipt.json": _json_bytes(brief.get("receipt") or {}),
        "05-source-proofs.json": _json_bytes(brief.get("source_proofs") or []),
    }
    for name, payload in (raw or {}).items():
        files[f"raw/{name}.json"] = _json_bytes(payload)
    checksums = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {name}\n" for name, content in sorted(files.items())
    )
    files["SHA256SUMS"] = checksums.encode("utf-8")
    when = _pack_time(brief)
    stamp = (when.year, when.month, when.day, when.hour, when.minute, when.second)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            info = zipfile.ZipInfo(filename=name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    return buffer.getvalue()
