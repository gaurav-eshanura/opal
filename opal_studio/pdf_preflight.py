"""
Opal - PDF/X & Archival Preflight Engine (Acrobat Pro Parity)
Plain English: This file inspects and validates PDFs against international printing
and archival standards (PDF/X-1a, PDF/X-3, PDF/X-4, PDF/A-1b, and Commercial Print).
It analyzes font embedding, image DPI resolution, color spaces, trim and bleed boxes,
transparency, and output intents. It also fixes non-compliant documents by injecting
standard trim boxes, color output intents, XMP metadata, and flattening transparency.
All processing runs locally on the user's computer without cloud servers or fees.
"""

import os
import re
import json
import io
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Any

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from PIL import Image
except ImportError:
    Image = None


# ---------------------------------------------------------------------------
# Profiles & Constants
# ---------------------------------------------------------------------------

class PreflightProfile:
    PDFX_1A = "PDF/X-1a:2001"
    PDFX_3 = "PDF/X-3:2002"
    PDFX_4 = "PDF/X-4:2010"
    PDFA_1B = "PDF/A-1b"
    COMMERCIAL_PRINT = "Commercial Print Ready"

    ALL = [PDFX_1A, PDFX_3, PDFX_4, PDFA_1B, COMMERCIAL_PRINT]


class CheckSeverity:
    ERROR = "error"      # Fails compliance
    WARNING = "warning"  # Advisory / potential print defect
    INFO = "info"        # Informational statistic


# Standard Output Condition presets for PDF/X and PDF/A
OUTPUT_INTENT_PRESETS = {
    "FOGRA39": {
        "id": "FOGRA39",
        "condition": "FOGRA39",
        "info": "Coated FOGRA39 (ISO 12647-2:2004)",
        "registry": "http://www.color.org",
    },
    "CGATS_TR001": {
        "id": "CGATS TR 001",
        "condition": "CGATS TR 001",
        "info": "SWOP (Coated paper, sheetfed)",
        "registry": "http://www.color.org",
    },
    "GRACoL2006": {
        "id": "GRACoL2006_Coated1v2",
        "condition": "GRACoL 2006",
        "info": "GRACoL 2006 Coated Commercial Sheetfed",
        "registry": "http://www.color.org",
    },
}


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class PreflightIssue:
    category: str        # font, image, geometry, color, transparency, metadata, security, interactivity
    severity: str        # error, warning, info
    page: int            # 1-based page number, or 0 for global document issue
    rule: str            # machine identifier
    message: str         # founder / user friendly description
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PreflightReport:
    path: str
    profile: str
    passed: bool
    error_count: int
    warning_count: int
    info_count: int
    page_count: int
    issues: List[PreflightIssue] = field(default_factory=list)
    fonts_summary: List[Dict[str, Any]] = field(default_factory=list)
    images_summary: List[Dict[str, Any]] = field(default_factory=list)
    geometry_summary: List[Dict[str, Any]] = field(default_factory=list)
    output_intents: List[Dict[str, Any]] = field(default_factory=list)
    has_transparency: bool = False
    is_encrypted: bool = False
    has_javascript: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        status_text = "PASS (Compliant)" if self.passed else "FAIL (Non-Compliant)"
        lines = [
            f"# Opal PDF Preflight Report",
            f"",
            f"- **Target Profile:** `{self.profile}`",
            f"- **Verdict:** **{status_text}**",
            f"- **File:** `{self.path}`",
            f"- **Total Pages:** {self.page_count}",
            f"- **Errors:** {self.error_count} · **Warnings:** {self.warning_count} · **Info:** {self.info_count}",
            f"",
            f"---",
            f"",
            f"## Issues Summary",
            f"",
        ]
        if not self.issues:
            lines.append("No issues found. Document satisfies all preflight requirements.")
        else:
            lines.append("| Severity | Page | Category | Issue |")
            lines.append("|---|---|---|---|")
            for issue in self.issues:
                page_str = f"Page {issue.page}" if issue.page > 0 else "Global"
                lines.append(f"| `{issue.severity.upper()}` | {page_str} | {issue.category} | {issue.message} |")

        lines.extend([
            f"",
            f"---",
            f"",
            f"## Asset Inspection",
            f"",
            f"- **Fonts Detected:** {len(self.fonts_summary)}",
            f"- **Images Inspected:** {len(self.images_summary)}",
            f"- **Transparency Present:** {'Yes' if self.has_transparency else 'No'}",
            f"- **OutputIntents Embedded:** {len(self.output_intents)}",
            f"- **Encryption / Lock:** {'Yes (Forbidden in PDF/X)' if self.is_encrypted else 'No (Clean)'}",
            f"- **Interactive Scripts:** {'Yes (Forbidden in PDF/X & PDF/A)' if self.has_javascript else 'No'}",
        ])
        return "\n".join(lines)

    def to_html(self) -> str:
        status_color = "#37C98A" if self.passed else "#EE4E8A"
        status_text = "COMPLIANT" if self.passed else "NON-COMPLIANT"

        issue_rows = []
        for issue in self.issues:
            sev_color = "#EE4E8A" if issue.severity == CheckSeverity.ERROR else "#FF9A3C" if issue.severity == CheckSeverity.WARNING else "#6C63FF"
            page_text = f"Page {issue.page}" if issue.page > 0 else "Global"
            issue_rows.append(f"""
            <tr>
              <td><span style="background:{sev_color}22; color:{sev_color}; padding:3px 8px; border-radius:12px; font-weight:700; font-size:11px;">{issue.severity.upper()}</span></td>
              <td style="color:#A8B2C8; font-size:12px;">{page_text}</td>
              <td style="color:#A8B2C8; font-size:12px;">{issue.category}</td>
              <td style="color:#EDF1FA; font-size:12px;">{issue.message}</td>
            </tr>
            """)
        if not issue_rows:
            issues_tbody = "<tr><td colspan='4' style='color:#37C98A; text-align:center; padding:16px;'>✓ Document meets all standard specifications without defects.</td></tr>"
        else:
            issues_tbody = "\n".join(issue_rows)

        font_rows = []
        for f in self.fonts_summary:
            emb_badge = '<span style="color:#37C98A;">✓ Embedded</span>' if f.get("embedded") else '<span style="color:#EE4E8A;">✕ Unembedded</span>'
            pages_list = ", ".join(str(p) for p in f.get("pages", []))
            font_rows.append(f"<tr><td style='color:#EDF1FA;'>{f.get('name')}</td><td style='color:#A8B2C8;'>{f.get('type')}</td><td>{emb_badge}</td><td style='color:#A8B2C8;'>Pages: {pages_list}</td></tr>")
        fonts_tbody = "\n".join(font_rows) if font_rows else "<tr><td colspan='4' style='color:#A8B2C8; padding:8px;'>No text fonts referenced.</td></tr>"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Opal Preflight Inspection Report</title>
  <style>
    body {{ background: #0B0E18; color: #EDF1FA; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif; margin: 0; padding: 32px; }}
    .container {{ max-width: 900px; margin: 0 auto; }}
    .card {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.12); border-radius: 16px; padding: 24px; margin-bottom: 24px; }}
    .badge {{ display: inline-block; padding: 6px 14px; border-radius: 20px; font-weight: 700; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.08); }}
    th {{ color: #A8B2C8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }}
    h1, h2, h3 {{ margin-top: 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="card" style="border-top: 3px solid {status_color};">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <h1 style="font-size:24px; margin-bottom:4px;">Opal PDF Preflight Report</h1>
          <div style="color:#A8B2C8; font-size:13px;">Target Profile: <strong style="color:#EDF1FA;">{self.profile}</strong> · File: {Path(self.path).name}</div>
        </div>
        <div>
          <span class="badge" style="background:{status_color}22; color:{status_color}; border:1px solid {status_color}55;">● {status_text}</span>
        </div>
      </div>
      <div style="display:flex; gap:24px; margin-top:20px; border-top:1px solid rgba(255,255,255,0.08); padding-top:16px;">
        <div><span style="font-size:20px; font-weight:700; color:{'#EE4E8A' if self.error_count > 0 else '#37C98A'};">{self.error_count}</span> <span style="color:#A8B2C8; font-size:12px;">Errors</span></div>
        <div><span style="font-size:20px; font-weight:700; color:#FF9A3C;">{self.warning_count}</span> <span style="color:#A8B2C8; font-size:12px;">Warnings</span></div>
        <div><span style="font-size:20px; font-weight:700; color:#6C63FF;">{self.info_count}</span> <span style="color:#A8B2C8; font-size:12px;">Info</span></div>
        <div><span style="font-size:20px; font-weight:700; color:#EDF1FA;">{self.page_count}</span> <span style="color:#A8B2C8; font-size:12px;">Pages</span></div>
      </div>
    </div>

    <div class="card">
      <h2 style="font-size:16px;">Inspection Findings</h2>
      <table>
        <thead>
          <tr><th>Severity</th><th>Location</th><th>Category</th><th>Details</th></tr>
        </thead>
        <tbody>
          {issues_tbody}
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2 style="font-size:16px;">Embedded Font Catalog</h2>
      <table>
        <thead>
          <tr><th>Font Family</th><th>Format</th><th>Status</th><th>Distribution</th></tr>
        </thead>
        <tbody>
          {fonts_tbody}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Preflight Inspection Engine
# ---------------------------------------------------------------------------

def run_preflight(
    doc_or_path: Any,
    profile: str = PreflightProfile.PDFX_1A,
    min_image_dpi: float = 300.0,
    warn_image_dpi: float = 150.0,
) -> PreflightReport:
    """
    Executes an offline preflight check against the designated standard profile.
    Accepts either an open PyMuPDF Document or a file path string.
    """
    if not fitz:
        raise RuntimeError("PDF engine (PyMuPDF) is not installed.")

    should_close = False
    if isinstance(doc_or_path, (str, Path)):
        doc = fitz.open(str(doc_or_path))
        doc_path = str(doc_or_path)
        should_close = True
    else:
        doc = doc_or_path
        doc_path = getattr(doc, "name", "document.pdf")

    try:
        issues: List[PreflightIssue] = []
        fonts_summary: List[Dict[str, Any]] = []
        images_summary: List[Dict[str, Any]] = []
        geometry_summary: List[Dict[str, Any]] = []
        output_intents: List[Dict[str, Any]] = []

        is_encrypted = bool(getattr(doc, "is_encrypted", False))
        page_count = len(doc)
        has_transparency = False
        has_javascript = False

        # 1. Global Security & Encryption
        if is_encrypted:
            issues.append(PreflightIssue(
                category="security",
                severity=CheckSeverity.ERROR,
                page=0,
                rule="document-encrypted",
                message="Document is password encrypted. ISO PDF/X and PDF/A standards forbid encryption.",
            ))

        # 2. Output Intents Check
        catalog_xref = doc.pdf_catalog()
        oi_type, oi_val = doc.xref_get_key(catalog_xref, "OutputIntents")
        if oi_type == "array" and oi_val.strip() not in ("[]", "null"):
            # Parse references in array
            refs = re.findall(r"(\d+)\s+0\s+R", oi_val)
            for ref_str in refs:
                xref_id = int(ref_str)
                obj_text = doc.xref_object(xref_id)
                subtype_m = re.search(r"/S\s+/([A-Za-z0-9_]+)", obj_text)
                ident_m = re.search(r"/OutputConditionIdentifier\s*\((.*?)\)", obj_text)
                cond_m = re.search(r"/OutputCondition\s*\((.*?)\)", obj_text)
                info_m = re.search(r"/Info\s*\((.*?)\)", obj_text)
                output_intents.append({
                    "xref": xref_id,
                    "subtype": subtype_m.group(1) if subtype_m else "",
                    "identifier": ident_m.group(1) if ident_m else "",
                    "condition": cond_m.group(1) if cond_m else "",
                    "info": info_m.group(1) if info_m else "",
                })

        if profile in (PreflightProfile.PDFX_1A, PreflightProfile.PDFX_3, PreflightProfile.PDFX_4):
            if not output_intents:
                issues.append(PreflightIssue(
                    category="metadata",
                    severity=CheckSeverity.ERROR,
                    page=0,
                    rule="missing-output-intent",
                    message="Missing OutputIntent. PDF/X requires a defined output profile (e.g. FOGRA39 or CGATS TR 001).",
                ))
            else:
                has_pdfx_oi = any(oi["subtype"] == "GTS_PDFX" for oi in output_intents)
                if not has_pdfx_oi:
                    issues.append(PreflightIssue(
                        category="metadata",
                        severity=CheckSeverity.ERROR,
                        page=0,
                        rule="invalid-output-intent-subtype",
                        message="OutputIntent present but missing /S /GTS_PDFX subtype.",
                    ))
        elif profile == PreflightProfile.PDFA_1B:
            if not output_intents:
                issues.append(PreflightIssue(
                    category="metadata",
                    severity=CheckSeverity.ERROR,
                    page=0,
                    rule="missing-pdfa-output-intent",
                    message="Missing OutputIntent. PDF/A requires an embedded ICC output condition dictionary.",
                ))

        # 3. Interactive Scripts (JavaScript)
        names_type, names_val = doc.xref_get_key(catalog_xref, "Names")
        if "JavaScript" in str(names_val):
            has_javascript = True
        js_type, js_val = doc.xref_get_key(catalog_xref, "JavaScript")
        if js_type != "null":
            has_javascript = True

        if has_javascript and profile in (PreflightProfile.PDFX_1A, PreflightProfile.PDFX_3, PreflightProfile.PDFA_1B):
            issues.append(PreflightIssue(
                category="interactivity",
                severity=CheckSeverity.ERROR,
                page=0,
                rule="forbidden-javascript",
                message="Document contains embedded JavaScript actions, which are prohibited in archival and blind print standards.",
            ))

        # 4. Page by Page Asset Inspection
        seen_font_keys = set()

        for page_idx in range(page_count):
            page_num = page_idx + 1
            page = doc[page_idx]

            # Geometry inspection
            mb = page.mediabox
            cb = page.cropbox
            tb = page.trimbox
            bb = page.bleedbox

            has_explicit_trim = (doc.xref_get_key(page.xref, "TrimBox")[0] != "null")
            has_explicit_bleed = (doc.xref_get_key(page.xref, "BleedBox")[0] != "null")

            geometry_summary.append({
                "page": page_num,
                "mediabox": [mb.x0, mb.y0, mb.x1, mb.y1],
                "cropbox": [cb.x0, cb.y0, cb.x1, cb.y1],
                "trimbox": [tb.x0, tb.y0, tb.x1, tb.y1],
                "bleedbox": [bb.x0, bb.y0, bb.x1, bb.y1],
                "explicit_trim": has_explicit_trim,
                "explicit_bleed": has_explicit_bleed,
            })

            if profile in (PreflightProfile.PDFX_1A, PreflightProfile.PDFX_3, PreflightProfile.PDFX_4):
                if not has_explicit_trim:
                    issues.append(PreflightIssue(
                        category="geometry",
                        severity=CheckSeverity.ERROR,
                        page=page_num,
                        rule="missing-trimbox",
                        message=f"Page {page_num} is missing an explicit TrimBox. Professional print workflows require defined cut lines.",
                        details={"mediabox": [mb.x0, mb.y0, mb.x1, mb.y1]},
                    ))

            # Fonts Inspection
            page_fonts = page.get_fonts(full=True)
            for font_item in page_fonts:
                # font_item: (xref, ext, type, basefont, name, encoding, buffer)
                f_xref = font_item[0]
                f_ext = font_item[1]
                f_type = font_item[2]
                f_name = font_item[3]
                is_embedded = (f_ext != "n/a")

                font_key = (f_name, f_type)
                if font_key not in seen_font_keys:
                    seen_font_keys.add(font_key)
                    fonts_summary.append({
                        "name": f_name,
                        "type": f_type,
                        "embedded": is_embedded,
                        "pages": [page_num],
                        "xref": f_xref,
                    })
                else:
                    for entry in fonts_summary:
                        if entry["name"] == f_name and entry["type"] == f_type:
                            if page_num not in entry["pages"]:
                                entry["pages"].append(page_num)

                # Strict font embedding requirement for PDF/X and PDF/A
                if not is_embedded:
                    if profile in (PreflightProfile.PDFX_1A, PreflightProfile.PDFX_3, PreflightProfile.PDFX_4, PreflightProfile.PDFA_1B):
                        issues.append(PreflightIssue(
                            category="font",
                            severity=CheckSeverity.ERROR,
                            page=page_num,
                            rule="font-not-embedded",
                            message=f"Font '{f_name}' ({f_type}) is not embedded on page {page_num}. All fonts must be 100% embedded.",
                            details={"font": f_name, "type": f_type},
                        ))
                    else:
                        issues.append(PreflightIssue(
                            category="font",
                            severity=CheckSeverity.WARNING,
                            page=page_num,
                            rule="font-not-embedded",
                            message=f"Font '{f_name}' is not embedded. It may render differently across operating systems.",
                            details={"font": f_name, "type": f_type},
                        ))

            # Images Inspection
            page_images = page.get_images()
            for img_item in page_images:
                # img_item: (xref, smask, width, height, bpc, colorspace, alt_cs, name, filter)
                img_xref = img_item[0]
                smask = img_item[1]
                img_w = img_item[2]
                img_h = img_item[3]
                colorspace = img_item[5]

                # Check transparency on image
                if smask > 0:
                    has_transparency = True
                    if profile in (PreflightProfile.PDFX_1A, PreflightProfile.PDFX_3, PreflightProfile.PDFA_1B):
                        issues.append(PreflightIssue(
                            category="transparency",
                            severity=CheckSeverity.ERROR,
                            page=page_num,
                            rule="image-softmask-transparency",
                            message=f"Image on page {page_num} uses a soft mask transparency layer, which is forbidden in {profile}.",
                            details={"xref": img_xref},
                        ))

                # Color space checks for PDF/X-1a (Must be CMYK or DeviceGray)
                if profile == PreflightProfile.PDFX_1A:
                    if colorspace in ("DeviceRGB", "ICCBased") and "rgb" in colorspace.lower():
                        issues.append(PreflightIssue(
                            category="color",
                            severity=CheckSeverity.ERROR,
                            page=page_num,
                            rule="forbidden-rgb-color",
                            message=f"Image on page {page_num} uses RGB color space ({colorspace}). PDF/X-1a strictly requires CMYK or Grayscale.",
                            details={"xref": img_xref, "colorspace": colorspace},
                        ))

                # Calculate effective DPI
                rects = page.get_image_rects(img_xref)
                for rect in rects:
                    dpi_x = (img_w / rect.width) * 72.0 if rect.width > 0 else 0.0
                    dpi_y = (img_h / rect.height) * 72.0 if rect.height > 0 else 0.0
                    eff_dpi = min(dpi_x, dpi_y)

                    images_summary.append({
                        "page": page_num,
                        "xref": img_xref,
                        "width": img_w,
                        "height": img_h,
                        "colorspace": colorspace,
                        "dpi_x": round(dpi_x, 1),
                        "dpi_y": round(dpi_y, 1),
                        "effective_dpi": round(eff_dpi, 1),
                    })

                    if eff_dpi < warn_image_dpi:
                        issues.append(PreflightIssue(
                            category="image",
                            severity=CheckSeverity.WARNING,
                            page=page_num,
                            rule="low-image-resolution",
                            message=f"Image on page {page_num} has low resolution ({eff_dpi:.0f} DPI, below {warn_image_dpi:.0f} DPI threshold). It may print blurry.",
                            details={"effective_dpi": eff_dpi, "width": img_w, "height": img_h},
                        ))
                    elif eff_dpi < min_image_dpi and profile in (PreflightProfile.PDFX_1A, PreflightProfile.COMMERCIAL_PRINT):
                        issues.append(PreflightIssue(
                            category="image",
                            severity=CheckSeverity.INFO,
                            page=page_num,
                            rule="suboptimal-image-resolution",
                            message=f"Image resolution on page {page_num} ({eff_dpi:.0f} DPI) is acceptable for office print, but below the 300 DPI high-end press target.",
                            details={"effective_dpi": eff_dpi},
                        ))

            # Page Transparency / ExtGState Checks
            res_type, res_val = doc.xref_get_key(page.xref, "Resources")
            if res_type == "xref":
                res_xref = int(res_val.split()[0])
                res_obj = doc.xref_object(res_xref)
                if "/ExtGState" in res_obj or "/SMask" in res_obj:
                    # Further check if blend modes or alpha < 1 are declared
                    if any(bm in res_obj for bm in ("/Multiply", "/Screen", "/Overlay", "/Darken", "/Lighten")):
                        has_transparency = True
                        if profile in (PreflightProfile.PDFX_1A, PreflightProfile.PDFX_3, PreflightProfile.PDFA_1B):
                            issues.append(PreflightIssue(
                                category="transparency",
                                severity=CheckSeverity.ERROR,
                                page=page_num,
                                rule="blend-mode-transparency",
                                message=f"Page {page_num} uses active blend mode transparency, which is prohibited in {profile}.",
                            ))

        # Compute tallies
        error_count = sum(1 for i in issues if i.severity == CheckSeverity.ERROR)
        warning_count = sum(1 for i in issues if i.severity == CheckSeverity.WARNING)
        info_count = sum(1 for i in issues if i.severity == CheckSeverity.INFO)
        passed = (error_count == 0)

        report = PreflightReport(
            path=doc_path,
            profile=profile,
            passed=passed,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            page_count=page_count,
            issues=issues,
            fonts_summary=fonts_summary,
            images_summary=images_summary,
            geometry_summary=geometry_summary,
            output_intents=output_intents,
            has_transparency=has_transparency,
            is_encrypted=is_encrypted,
            has_javascript=has_javascript,
        )
        return report

    finally:
        if should_close:
            doc.close()


# ---------------------------------------------------------------------------
# Automated Fixup & Conformance Converter
# ---------------------------------------------------------------------------

def apply_preflight_fixups(
    src_path: str,
    dest_path: str,
    profile: str = PreflightProfile.PDFX_1A,
    preset_name: str = "FOGRA39",
    trim_margin_pt: float = 9.0,
    flatten_transparency: bool = True,
    rasterize_unembedded_fonts: bool = True,
    raster_dpi: int = 300,
) -> PreflightReport:
    """
    Takes an input PDF and produces a standardized compliant document:
    1. Injects explicit TrimBox and BleedBox on every page.
    2. Embeds standard OutputIntent dictionary (FOGRA39 / CGATS).
    3. Strips prohibited JavaScript actions and unprotects document.
    4. Stamps standardized PDF/X or PDF/A XMP metadata package.
    5. Flattens transparent pages and unembedded fonts when strict PDF/X-1a is targeted.
    6. Verifies and returns a full post-conversion PreflightReport.
    """
    if not fitz:
        raise RuntimeError("PDF engine (PyMuPDF) is not installed.")

    src_p = Path(src_path)
    dest_p = Path(dest_path)
    tmp_dest = dest_p.with_name(f".{dest_p.name}.preflight_tmp")

    doc = fitz.open(str(src_p))

    try:
        # Step A: Flatten transparency or unembedded fonts if requested for compliance
        initial_check = run_preflight(doc, profile=profile)
        needs_raster = False
        if flatten_transparency and initial_check.has_transparency and profile in (PreflightProfile.PDFX_1A, PreflightProfile.PDFX_3, PreflightProfile.PDFA_1B):
            needs_raster = True
        if rasterize_unembedded_fonts and any(not f.get("embedded") for f in initial_check.fonts_summary) and profile in (PreflightProfile.PDFX_1A, PreflightProfile.PDFX_3, PreflightProfile.PDFA_1B):
            needs_raster = True

        if needs_raster:
            # Reconstruct document with rasterized high-resolution pages to eliminate all blend modes, alpha masks, and missing fonts
            flattened_doc = fitz.open()
            for page in doc:
                pix = page.get_pixmap(dpi=raster_dpi)
                new_page = flattened_doc.new_page(width=page.rect.width, height=page.rect.height)
                new_page.insert_image(page.rect, pixmap=pix)
            doc.close()
            doc = flattened_doc

        # Step B: Standardize Page Geometry (TrimBox & BleedBox)
        for page in doc:
            # Set bleed box to media box
            page.set_bleedbox(page.mediabox)

            # Set trim box with standard printer margin (default 9pt / 3.175mm) or match cropbox
            mb = page.mediabox
            if mb.width > (trim_margin_pt * 2) and mb.height > (trim_margin_pt * 2):
                trim_rect = fitz.Rect(
                    mb.x0 + trim_margin_pt,
                    mb.y0 + trim_margin_pt,
                    mb.x1 - trim_margin_pt,
                    mb.y1 - trim_margin_pt,
                )
            else:
                trim_rect = page.cropbox
            page.set_trimbox(trim_rect)

        # Step C: Embed Standard OutputIntent
        preset = OUTPUT_INTENT_PRESETS.get(preset_name, OUTPUT_INTENT_PRESETS["FOGRA39"])
        catalog_xref = doc.pdf_catalog()

        # Create output intent object
        oi_xref = doc.get_new_xref()
        subtype_tag = "GTS_PDFA1" if profile == PreflightProfile.PDFA_1B else "GTS_PDFX"
        oi_dict = f"""<<
  /Type /OutputIntent
  /S /{subtype_tag}
  /OutputConditionIdentifier ({preset['id']})
  /OutputCondition ({preset['condition']})
  /Info ({preset['info']})
  /RegistryName ({preset['registry']})
>>"""
        doc.update_object(oi_xref, oi_dict)
        doc.xref_set_key(catalog_xref, "OutputIntents", f"[{oi_xref} 0 R]")

        # Step D: Strip Forbidden JavaScript & Actions
        doc.xref_set_key(catalog_xref, "JavaScript", "null")
        names_type, names_val = doc.xref_get_key(catalog_xref, "Names")
        if "JavaScript" in str(names_val):
            doc.xref_set_key(catalog_xref, "Names", "null")

        # Step E: Stamp Standardized XMP Metadata
        if profile == PreflightProfile.PDFA_1B:
            xmp_packet = f"""<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/"
    pdfaid:part="1"
    pdfaid:conformance="B"/>
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:format>application/pdf</dc:format>
    <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{src_p.stem}</rdf:li></rdf:Alt></dc:title>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
        else:
            xmp_packet = f"""<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:pdfx="http://ns.adobe.com/pdfx/1.3/"
    xmlns:pdfxid="http://www.npes.org/pdfx/ns/id/"
    pdfx:GTS_PDFXVersion="{profile}"
    pdfxid:GTS_PDFXVersion="{profile}"/>
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:format>application/pdf</dc:format>
    <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{src_p.stem}</rdf:li></rdf:Alt></dc:title>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""

        doc.set_xml_metadata(xmp_packet)

        # Save to temporary destination
        tmp_dest.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(tmp_dest), garbage=4, deflate=True)
        doc.close()

        # Atomic replacement
        if dest_p.exists():
            dest_p.unlink()
        tmp_dest.replace(dest_p)

        # Verify the saved file
        return run_preflight(str(dest_p), profile=profile)

    except Exception:
        if tmp_dest.exists():
            tmp_dest.unlink(missing_ok=True)
        raise
    finally:
        if not doc.is_closed:
            doc.close()
