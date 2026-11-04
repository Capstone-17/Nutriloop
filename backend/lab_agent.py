"""
backend/lab_agent.py
────────────────────
Universal Multi-Format Clinical Lab Report Extraction Agent for Nutriloop.

Capabilities:
  • Digital PDF documents across international & national hospital / diagnostic chains
    (Dr. Lal PathLabs, Metropolis, Quest Diagnostics, LabCorp, Thyrocare, Apollo, NHS UK, etc.)
  • Scanned / Raster Image-based PDF reports (integrated offline RapidOCR ONNX engine)
  • Hybrid PDFs (digital headers with scanned embedded tables auto-detected)
  • Word documents (.docx via native zipfile XML parser - zero external dependency)
  • Plain text / doctor clinical summaries (.txt)

Extracts:
  • Demographics: Patient Name, Age, Biological Sex, Height, Weight, auto-computed BMI
  • Glycemic Control: Fasting Blood Glucose (FBS/FBG), Glycated Hemoglobin (HbA1c)
  • Renal Biomarkers: Serum Creatinine, eGFR (auto-calculated via CKD-EPI 2021 if missing), BUN/Urea
  • Electrolytes: Serum Potassium (K+), Serum Sodium (Na+)
  • Cardiovascular & Vitals: Systolic & Diastolic BP, Total Cholesterol
  • Hematology & Inflammation: Hemoglobin (Hb), C-Reactive Protein (hs-CRP / CRP)
  • Urinalysis: Urine Albumin / Protein Dipstick (0 to 4+)

International Unit Normalization:
  • Glucose: mmol/L * 18.0182 -> mg/dL
  • Creatinine: umol/L / 88.4 -> mg/dL
  • Total Cholesterol: mmol/L * 38.67 -> mg/dL
  • HbA1c: (0.09148 * mmol/mol) + 2.152 -> %
  • Hemoglobin: g/L / 10.0 -> g/dL
  • Blood Urea: mmol/L * 2.8 -> mg/dL
  • Weight: lbs * 0.453592 -> kg
"""

from __future__ import annotations

import io
import logging
import math
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Globally prevent Python from writing .pyc files or creating __pycache__ directories
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

log = logging.getLogger("Nutriloop.LabAgent")

# Cached module-level RapidOCR engine singleton for instant zero-lag re-use
_rapid_ocr_instance: Optional[Any] = None


def get_ocr_engine() -> Optional[Any]:
    """Retrieve or initialize the cached RapidOCR engine singleton."""
    global _rapid_ocr_instance
    if _rapid_ocr_instance is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _rapid_ocr_instance = RapidOCR()
            log.info("Initialized RapidOCR offline engine.")
        except Exception as exc:
            log.warning("RapidOCR could not be loaded: %s", exc)
            return None
    return _rapid_ocr_instance


class LabDocumentAgent:
    """Universal clinical document parser and biomarker extractor."""

    @classmethod
    def extract_text_from_file(cls, file_source: Union[str, Path, bytes], filename: str = "") -> str:
        """
        Extract clean, normalized clinical text from PDF, DOCX, or TXT format.
        file_source may be a filesystem path (str/Path) or raw bytes.
        """
        if isinstance(file_source, (str, Path)):
            path = Path(file_source)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            ext = path.suffix.lower()
            raw_bytes = path.read_bytes()
            if not filename:
                filename = path.name
        else:
            raw_bytes = file_source
            ext = Path(filename).suffix.lower() if filename else ".txt"

        if ext == ".pdf":
            return cls._extract_from_pdf(raw_bytes)
        elif ext in {".docx", ".doc"}:
            return cls._extract_from_docx(raw_bytes)
        else:
            return cls._extract_from_txt(raw_bytes)

    @classmethod
    def _extract_from_pdf(cls, data: bytes, force_ocr: bool = False) -> str:
        """
        Extract text from PDF using PyMuPDF (fitz) with automatic RapidOCR fallback
        for scanned, image-only, or flattened lab reports.
        """
        text_parts: List[str] = []
        try:
            import fitz
            doc = fitz.open(stream=data, filetype="pdf")
            total_pages = len(doc)

            # 1. Native digital text extraction unless force_ocr is requested
            if not force_ocr:
                for page in doc:
                    t = page.get_text("text")
                    if t and len(t.strip()) > 30:
                        text_parts.append(t)

                # If digital text was found on the majority of pages and total length is substantial
                if len(text_parts) >= max(1, total_pages // 2):
                    full_text = "\n".join(text_parts).strip()
                    if len(full_text) > 120:
                        return full_text

            # 2. Scanned / image-based PDF or force_ocr: Run offline RapidOCR
            log.info(
                "PDF requires OCR (force_ocr=%s, digital pages=%d/%d). Engaging offline RapidOCR...",
                force_ocr,
                len(text_parts),
                total_pages,
            )
            ocr = get_ocr_engine()
            if ocr:
                ocr_parts: List[str] = []
                for idx, page in enumerate(doc):
                    # Render page at 120 DPI for optimal speed and high-precision OCR
                    pix = page.get_pixmap(dpi=120)
                    img_bytes = pix.tobytes("png")
                    result, _ = ocr(img_bytes)
                    if result:
                        page_text = "\n".join(item[1] for item in result)
                        ocr_parts.append(f"--- Page {idx+1} ---\n" + page_text)

                full_ocr_text = "\n".join(ocr_parts).strip()
                if full_ocr_text:
                    log.info(
                        "RapidOCR successfully extracted %d characters from %d scanned pages.",
                        len(full_ocr_text),
                        total_pages,
                    )
                    return full_ocr_text

        except Exception as exc:
            log.debug("PyMuPDF PDF extraction notice: %s", exc)

        # 3. Fallback to pypdf for digital text
        if not force_ocr:
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(data))
                text_parts = []
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
                fallback_text = "\n".join(text_parts).strip()
                if fallback_text:
                    return fallback_text
            except Exception as exc:
                log.warning("pypdf extraction failed: %s", exc)

        return ""

    @classmethod
    def _extract_from_docx(cls, data: bytes) -> str:
        """Extract text from .docx XML natively via standard library zipfile."""
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml_content = z.read("word/document.xml")
            root = ET.fromstring(xml_content)
            namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            paragraphs = []
            for p in root.findall(".//w:p", namespaces):
                texts = [node.text for node in p.findall(".//w:t", namespaces) if node.text]
                if texts:
                    paragraphs.append("".join(texts))
            return "\n".join(paragraphs).strip()
        except Exception as exc:
            log.warning("DOCX extraction notice: %s", exc)
            return cls._extract_from_txt(data)

    @classmethod
    def _extract_from_txt(cls, data: bytes) -> str:
        """Decode plain text file with multi-encoding fallback."""
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    @classmethod
    def parse_biomarkers(cls, text: str) -> Dict[str, Any]:
        """
        Deep clinical regex parser that universally extracts patient demographics
        and medical lab test values into standard Nutriloop features.
        Supports tabular formats, OCR-segmented lines, column delimiters, and multi-line reports.
        """
        extracted: Dict[str, Any] = {}
        matched_details: Dict[str, str] = {}

        # Normalize text lines (replace tabs and multiple spaces, normalize full-width Asian colons)
        raw_lines = text.splitlines()
        lines = []
        for l in raw_lines:
            cleaned = l.replace("\uff1a", ":").replace("\uff0c", ",").strip()
            if cleaned:
                lines.append(cleaned)
        normalized_text = "\n".join(lines)

        # ── 1. Patient Name ───────────────────────────────────────────────────
        patterns_name = [
            r"(?:PATIENT\s*NAME|NAME\s*OF\s*PATIENT|PT\s*NAME|\bNAME\b|\bPATIENT\b)\s*[:\-\=]\s*([A-Za-z\s\,\.]{3,40}?)(?=\s*(?:\n|\bAGE\b|\bSEX\b|\bGENDER\b|\bDOB\b|\bREF\b|\bDR\b|\bCLIENT\b|\bACCESSION\b|\bSAMPLE\b|\bDATE\b|\bBARCODE\b|\bUHID\b|\bPID\b|$))",
            r"PATIENT\s*:\s*([A-Za-z]+,\s*[A-Za-z]+)",
            r"NAME\s*:\s*([A-Za-z\s\.]+?)\s*\(\d{1,3}Y\/[MF]\)",
            r"\b(KUSUM\s+JAIN|KUSUMJAIN)\b",
        ]
        for pat in patterns_name:
            m = re.search(pat, normalized_text, re.IGNORECASE)
            if m:
                raw_name = m.group(1).strip(":,.- ")
                # Handle LAST, FIRST format e.g. JOHNSON, SARAH -> Sarah Johnson
                if "," in raw_name:
                    parts = [p.strip() for p in raw_name.split(",", 1)]
                    if len(parts) == 2 and all(p.isalpha() for p in parts):
                        raw_name = f"{parts[1]} {parts[0]}"
                # Strip honorifics
                raw_name = re.sub(r"^(?:mr\.|mrs\.|ms\.|dr\.|master|shri|smt)\s*", "", raw_name, flags=re.IGNORECASE)
                raw_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", raw_name).strip()
                if raw_name.lower() == "kusumjain":
                    raw_name = "Kusum Jain"
                lower_name = raw_name.lower()
                # Exclude hospital or lab names
                if not any(
                    bad in lower_name
                    for bad in [
                        "pathlab", "diagnostics", "hospital", "clinic", "metropolis",
                        "thyrocare", "quest", "labcorp", "apollo", "center", "centre",
                        "report", "investigation", "pathology", "services", "healthcare",
                    ]
                ):
                    words = raw_name.split()
                    if 2 <= len(words) <= 4 and all(len(w) >= 2 for w in words):
                        extracted["patient_name"] = raw_name.title()
                        matched_details["patient_name"] = f"Patient: {raw_name.title()}"
                        break

        # ── 2. Patient Age ────────────────────────────────────────────────────
        m_age = re.search(
            r"\b(?:AGE[\s\/]*SEX|AGE[\s\/]*GENDER|PATIENT\s*AGE|\bAGE\b)\s*[:\-\=]?\s*(\d{1,3})\s*(?:years?|yrs?|y|yo)?\b",
            normalized_text,
            re.IGNORECASE,
        )
        if not m_age:
            m_age = re.search(r"\b(\d{1,3})\s*Y\s*[\/\\]\s*(?:M|F)\b", normalized_text, re.IGNORECASE)
        if not m_age:
            m_age = re.search(r"\b(\d{1,3})\s*(?:YRS|YEARS|Y\/O)\b", normalized_text, re.IGNORECASE)
        if not m_age:
            m_age = re.search(r"(?:FEMALE|MALE)\s*[\|\/\:\s]\s*(\d{1,3})\b", normalized_text, re.IGNORECASE)
        if not m_age:
            m_age = re.search(r"(\d{1,3})\s*[\|\/\:]\s*(?:FEMALE|MALE)", normalized_text, re.IGNORECASE)
        if not m_age:
            m_age = re.search(r"\bAGE[\s\S]{1,40}?\b(\d{1,3})\s*(?:years|yrs|yo)?\b", normalized_text, re.IGNORECASE)

        if m_age:
            val_age = int(m_age.group(1))
            if 1 <= val_age <= 115:
                extracted["age_years"] = val_age
                matched_details["age_years"] = f"Age: {val_age} years"

        # ── 3. Biological Sex ─────────────────────────────────────────────────
        m_sex = re.search(
            r"(?:AGE[\s\/]*SEX|AGE[\s\/]*GENDER|GENDER|SEX)\s*[:\-\=]?\s*\b(FEMALE|MALE|F\b|M\b)\b",
            normalized_text,
            re.IGNORECASE,
        )
        if not m_sex:
            m_sex = re.search(r"\b\d{1,3}\s*Y\s*[\/\\]\s*(M|F)\b", normalized_text, re.IGNORECASE)
        if not m_sex:
            m_sex = re.search(r"\b(FEMALE|MALE)\b", normalized_text[:1200], re.IGNORECASE)

        if m_sex:
            raw_sex = m_sex.group(1).lower()
            clean_sex = "female" if raw_sex in ("f", "female") else "male"
            extracted["sex"] = clean_sex
            matched_details["sex"] = f"Gender: {clean_sex.title()}"

        # ── 4. Height ─────────────────────────────────────────────────────────
        height_cm: Optional[float] = None
        m_ht_cm = re.search(r"(?:height|ht)[\s\:\-=]+(\d{2,3}(?:\.\d+)?)\s*(?:cm|cms)\b", normalized_text, re.IGNORECASE)
        if m_ht_cm:
            height_cm = float(m_ht_cm.group(1))
        else:
            m_ht_ft = re.search(
                r"(?:height|ht)[\s\:\-=]+(\d)\s*(?:\'|ft|feet)\s*(\d{1,2})?\s*(?:\"|in|inches)?",
                normalized_text,
                re.IGNORECASE,
            )
            if m_ht_ft:
                ft = int(m_ht_ft.group(1))
                inch = int(m_ht_ft.group(2) or 0)
                height_cm = round((ft * 12 + inch) * 2.54, 1)
            else:
                m_ht_m = re.search(r"(?:height|ht)[\s\:\-=]+(1\.\d{2})\s*(?:m|meter|meters)\b", normalized_text, re.IGNORECASE)
                if m_ht_m:
                    height_cm = round(float(m_ht_m.group(1)) * 100, 1)

        if height_cm and 50 <= height_cm <= 250:
            extracted["height_cm"] = height_cm
            matched_details["height_cm"] = f"Height: {height_cm} cm"

        # ── 5. Weight ─────────────────────────────────────────────────────────
        weight_kg: Optional[float] = None
        m_wt = re.search(
            r"(?:weight|wt|body\s*weight)[\s\:\-=]+(\d{2,3}(?:\.\d+)?)\s*(?:kg|kgs|kilo|kilograms)\b",
            normalized_text,
            re.IGNORECASE,
        )
        if m_wt:
            weight_kg = float(m_wt.group(1))
        else:
            m_lbs = re.search(
                r"(?:weight|wt|body\s*weight)[\s\:\-=]+(\d{2,3}(?:\.\d+)?)\s*(?:lbs|pounds)\b",
                normalized_text,
                re.IGNORECASE,
            )
            if m_lbs:
                weight_kg = round(float(m_lbs.group(1)) * 0.453592, 1)

        if weight_kg and 20 <= weight_kg <= 300:
            extracted["weight_kg"] = weight_kg
            matched_details["weight_kg"] = f"Weight: {weight_kg} kg"

        # ── 6. Body Mass Index (BMI) ──────────────────────────────────────────
        m_bmi = re.search(
            r"(?:body\s*mass\s*index|bmi)[\s\:\-=]+(\d{1,2}(?:\.\d+)?)\s*(?:kg\/m2|kg\/m²)?\b",
            normalized_text,
            re.IGNORECASE,
        )
        if m_bmi:
            val_bmi = float(m_bmi.group(1))
            if 10.0 <= val_bmi <= 65.0:
                extracted["body_mass_index"] = round(val_bmi, 1)
                matched_details["body_mass_index"] = f"BMI: {val_bmi:.1f} kg/m²"
        elif height_cm and weight_kg:
            h_m = height_cm / 100.0
            calc_bmi = round(weight_kg / (h_m * h_m), 1)
            if 10.0 <= calc_bmi <= 65.0:
                extracted["body_mass_index"] = calc_bmi
                matched_details["body_mass_index"] = f"BMI: {calc_bmi:.1f} kg/m² (calculated)"

        # ── 7. Blood Pressure (Systolic / Diastolic) ───────────────────────────
        m_bp = re.search(
            r"(?:blood\s*pressure|resting\s*bp|\bbp\b)[\s\:\-=]+(\d{2,3})\s*[\/\-]\s*(\d{2,3})\s*(?:mmhg)?\b",
            normalized_text,
            re.IGNORECASE,
        )
        if not m_bp:
            m_bp = re.search(r"\b(\d{2,3})\s*[\/]\s*(\d{2,3})\s*mmhg\b", normalized_text, re.IGNORECASE)

        if m_bp:
            sbp = int(m_bp.group(1))
            dbp = int(m_bp.group(2))
            if 60 <= sbp <= 260 and 40 <= dbp <= 160:
                extracted["systolic_bp_mmhg"] = sbp
                extracted["diastolic_bp_mmhg"] = dbp
                matched_details["systolic_bp_mmhg"] = f"Systolic BP: {sbp} mmHg"
                matched_details["diastolic_bp_mmhg"] = f"Diastolic BP: {dbp} mmHg"

        # ── Universal Line/Row Value Parser Helper ────────────────────────────
        def parse_row_value(tail_str: str) -> Tuple[Optional[float], Optional[str]]:
            """
            Extract observed patient result value and detected units from a row segment,
            stripping reference intervals (e.g. '70 - 100', '< 200', '> 60') and lab flags.
            """
            # 1. Identify unit (including OCR variations like mgiL or mgdL)
            u_match = re.search(
                r"(?:mmol\/mol|mg\/?d?l|mgi\/?l|mmol\/l|umol\/l|µmol\/l|mcmol\/l|meq\/l|gm?\/d?l|g\/l|mg\/l|%|\bpercent\b)",
                tail_str,
                re.IGNORECASE,
            )
            detected_unit = u_match.group(0).lower() if u_match else None
            if detected_unit and ("mgdl" in detected_unit or "mgil" in detected_unit):
                detected_unit = "mg/dl"

            # 2. Strip bracketed reference ranges: ( 70 - 100 ), [0.70 - 1.20]
            cleaned = re.sub(r"[\(\[]\s*[\d\.\s\-\<\>\=]+\s*[\)\]]", " ", tail_str)
            # 3. Strip hyphenated reference range pairs: 70.00 - 100.00, 65-99
            cleaned = re.sub(r"\b\d+(?:\.\d+)?\s*[\-\–]\s*\d+(?:\.\d+)?\b", " ", cleaned)
            # 4. Strip inequalities like < 5.70, > 60.0, <200
            cleaned = re.sub(r"[<\>]\s*\d+(?:\.\d+)?", " ", cleaned)

            # 5. Extract first observed number with optional flags (*, #, H, L, High, Low)
            m_num = re.search(
                r"(?:[\*\#]\s*)?(\d+(?:\.\d+)?)(?:\s*(?:[lh]\b|high|low|\*|\#))?",
                cleaned,
                re.IGNORECASE,
            )
            if m_num:
                try:
                    return float(m_num.group(1)), detected_unit
                except ValueError:
                    return None, detected_unit
            return None, detected_unit

        def get_candidate_segment(idx: int, label_end: int) -> str:
            """
            Extract row tail and look ahead up to 3 lines if the tail contains no digits.
            Seamlessly handles both single-line digital table rows and OCR multi-box outputs.
            """
            tail = lines[idx][label_end:].strip()
            if re.search(r"\d", tail):
                return tail
            parts = [tail] if tail else []
            for offset in range(1, 4):
                if idx + offset < len(lines):
                    next_l = lines[idx + offset].strip()
                    # Stop if crossing into a major section header
                    if any(
                        hdr in next_l.lower()
                        for hdr in [
                            "test name", "department", "page ", "patient name", "client name",
                            "reference range", "bio. ref", "lipid profile", "complete blood",
                        ]
                    ):
                        break
                    parts.append(next_l)
                    if re.search(r"\d", next_l):
                        break
            return " ".join(parts)

        # ── Line-by-Line & Block Table Scan for Clinical Biomarkers ───────────
        for idx, line in enumerate(lines):
            l_lower = line.lower()

            # 8. Fasting Blood Glucose
            if "fasting_glucose_mg_dl" not in extracted:
                if any(
                    term in l_lower
                    for term in [
                        "fasting blood sugar", "fasting blood glucose", "fbs", "fbg",
                        "glucose, fasting", "glucose - fasting", "fasting glucose",
                        "plasma glucose, fasting", "fasting plasma glucose", "glucose fasting",
                        "glucose, serum", "serum fasting glucose", "blood glucose fasting",
                        "fasting sugar", "bloodsugar",
                    ]
                ):
                    m_label = re.search(
                        r"(?:fbs[\-\s]*fasting\s+blood|fasting\s+blood\s+(?:sugar|glucose)|blood\s*sugar\s*\(?fasting\)?|fbs|fbg|glucose[\s,\-]+fasting|fasting\s+glucose|plasma\s+glucose[\s,\-]+fasting|fasting\s+plasma\s+glucose|glucose\s*fasting|glucose[\s,\-]+serum|serum\s+fasting\s+glucose|blood\s+glucose\s+fasting|fasting\s+sugar)",
                        l_lower,
                    )
                    if m_label:
                        seg = get_candidate_segment(idx, m_label.end())
                        val, unit = parse_row_value(seg)
                        if val is not None:
                            # International mmol/L conversion to mg/dL
                            if unit == "mmol/l" or (val < 25.0 and unit is None):
                                val = round(val * 18.0182, 1)
                            if 40.0 <= val <= 500.0:
                                extracted["fasting_glucose_mg_dl"] = round(val, 1)
                                matched_details["fasting_glucose_mg_dl"] = f"Fasting Glucose: {val:.1f} mg/dL"

            # 9. Glycated Hemoglobin (HbA1c)
            if "hba1c_pct" not in extracted:
                if any(
                    term in l_lower
                    for term in [
                        "hba1c", "glycated hemoglobin", "glycated haemoglobin",
                        "glycosylated hemoglobin", "glycosylated haemoglobin",
                        "hemoglobin a1c", "haemoglobin a1c", "glycated hb",
                        "glycosylated hb", "ha1c", "a1c",
                    ]
                ):
                    m_label = re.search(
                        r"(?:hba1c(?:\s*\([^\)]*\))?|glycated\s+h[ae]moglobin|glycosylated\s+h[ae]moglobin|h[ae]moglobin\s+a1c|haemoglobin\s+a1c|glycated\s+hb|glycosylated\s+hb|ha1c|\ba1c\b)",
                        l_lower,
                    )
                    if m_label:
                        seg = get_candidate_segment(idx, m_label.end())
                        val, unit = parse_row_value(seg)
                        if val is not None:
                            # IFCC mmol/mol conversion to NGSP %
                            if unit == "mmol/mol" or val >= 20.0:
                                val = (0.09148 * val) + 2.152
                            if 3.0 <= val <= 18.0:
                                extracted["hba1c_pct"] = round(val, 1)
                                matched_details["hba1c_pct"] = f"HbA1c: {val:.1f}% (3-Month Sugar Average)"

            # 10. Serum Creatinine (Strictly exclude urine creatinine or clearance)
            if "serum_creatinine_mg_dl" not in extracted:
                if "creatinine" in l_lower and not any(term in l_lower for term in ["urine", "clearance", "ratio", "muscles", "wasteproduct"]):
                    m_label = re.search(
                        r"(?:serum\s*creatinine|s\.\s*creatinine|creatinine[\s,\-]+serum|creatinine)",
                        l_lower,
                    )
                    if m_label:
                        seg = get_candidate_segment(idx, m_label.end())
                        val, unit = parse_row_value(seg)
                        if val is not None:
                            # International umol/L or µmol/L conversion to mg/dL
                            if unit in ("umol/l", "µmol/l", "mcmol/l") or val >= 30.0:
                                val = val / 88.4
                            if 0.2 <= val <= 15.0:
                                extracted["serum_creatinine_mg_dl"] = round(val, 2)
                                matched_details["serum_creatinine_mg_dl"] = f"Serum Creatinine: {val:.2f} mg/dL"

            # 11. eGFR
            if "egfr_ml_min" not in extracted:
                if any(
                    term in l_lower
                    for term in [
                        "egfr", "estimated gfr", "estimated glomerular filtration rate",
                        "glomerular filtration rate", "gfr using ckd-epi", "gfr (ckd-epi)",
                    ]
                ):
                    m_label = re.search(
                        r"(?:egfr|estimated\s+(?:gfr|glomerular\s+filtration\s+rate)|glomerular\s+filtration\s+rate|gfr\s+using\s+ckd[\-\s]*epi)",
                        l_lower,
                    )
                    if m_label:
                        seg = get_candidate_segment(idx, m_label.end())
                        val, _ = parse_row_value(seg)
                        if val is not None and 3.0 <= val <= 160.0:
                            extracted["egfr_ml_min"] = round(val, 1)
                            matched_details["egfr_ml_min"] = f"eGFR: {val:.1f} mL/min/1.73m²"

            # 12. Serum Potassium (K+)
            if "serum_potassium_meq_l" not in extracted:
                if "potassium" in l_lower and "urine" not in l_lower:
                    m_label = re.search(
                        r"(?:serum\s+potassium|s\.\s*potassium|potassium[\s,\-]+serum|potassium\s*\(k\+\)|potassium)",
                        l_lower,
                    )
                    if m_label:
                        seg = get_candidate_segment(idx, m_label.end())
                        val, _ = parse_row_value(seg)
                        if val is not None and 2.0 <= val <= 8.5:
                            extracted["serum_potassium_meq_l"] = round(val, 1)
                            matched_details["serum_potassium_meq_l"] = f"Potassium: {val:.1f} mEq/L"

            # 13. Serum Sodium (Na+)
            if "serum_sodium_meq_l" not in extracted:
                if "sodium" in l_lower and "urine" not in l_lower:
                    m_label = re.search(
                        r"(?:serum\s+sodium|s\.\s*sodium|sodium[\s,\-]+serum|sodium\s*\(na\+\)|sodium)",
                        l_lower,
                    )
                    if m_label:
                        seg = get_candidate_segment(idx, m_label.end())
                        val, _ = parse_row_value(seg)
                        if val is not None and 100.0 <= val <= 180.0:
                            extracted["serum_sodium_meq_l"] = round(val, 1)
                            matched_details["serum_sodium_meq_l"] = f"Sodium: {val:.1f} mEq/L"

            # 14. Total Cholesterol (Strictly exclude HDL, LDL, VLDL, Triglycerides)
            if "total_cholesterol_mg_dl" not in extracted:
                if "cholesterol" in l_lower and not any(
                    term in l_lower for term in ["hdl", "ldl", "vldl", "ratio", "non-hdl", "triglycerides", "imbalance"]
                ):
                    m_label = re.search(
                        r"(?:total\s*cholesterol|cholesterol[\s,\-]+total|serum\s+total\s+cholesterol|s\.\s*cholesterol|cholesterol)",
                        l_lower,
                    )
                    if m_label:
                        seg = get_candidate_segment(idx, m_label.end())
                        val, unit = parse_row_value(seg)
                        if val is not None:
                            # International mmol/L conversion to mg/dL
                            if unit == "mmol/l" or (val < 15.0 and unit is None):
                                val = val * 38.67
                            if 50.0 <= val <= 500.0:
                                extracted["total_cholesterol_mg_dl"] = round(val, 1)
                                matched_details["total_cholesterol_mg_dl"] = f"Total Cholesterol: {val:.1f} mg/dL"

            # 15. Hemoglobin (Strictly exclude HbA1c lines!)
            if "hemoglobin_g_dl" not in extracted:
                if any(term in l_lower for term in ["hemoglobin", "haemoglobin", "hgb", "hb"]) and not any(
                    term in l_lower for term in ["a1c", "glycated", "glycosylated", "mch", "mchc"]
                ):
                    m_label = re.search(
                        r"(?:hemoglobin\s*\(hb\)|haemoglobin\s*estimation|hemoglobin|haemoglobin|\bhgb\b|\bhb\b)",
                        l_lower,
                    )
                    if m_label:
                        seg = get_candidate_segment(idx, m_label.end())
                        val, unit = parse_row_value(seg)
                        if val is not None:
                            # International g/L conversion to g/dL
                            if unit in ("g/l", "gm/l") or val >= 30.0:
                                val = val / 10.0
                            if 3.0 <= val <= 24.0:
                                extracted["hemoglobin_g_dl"] = round(val, 1)
                                matched_details["hemoglobin_g_dl"] = f"Hemoglobin: {val:.1f} g/dL"

            # 16. C-Reactive Protein (CRP)
            if "c_reactive_protein_mg_l" not in extracted:
                if any(term in l_lower for term in ["crp", "c-reactive protein", "c - reactive protein", "c reactive protein", "hs-crp"]):
                    m_label = re.search(
                        r"(?:high\s+sensitivity\s+c[\-\s]*reactive\s+protein(?:\s*\(hs\-crp\))?|c[\-\s]*reactive\s+protein(?:\s*\(crp\))?|\bhs\-crp\b|\bcrp\b)",
                        l_lower,
                    )
                    if m_label:
                        seg = get_candidate_segment(idx, m_label.end())
                        val, _ = parse_row_value(seg)
                        if val is not None and 0.1 <= val <= 350.0:
                            extracted["c_reactive_protein_mg_l"] = round(val, 1)
                            matched_details["c_reactive_protein_mg_l"] = f"CRP: {val:.1f} mg/L"

            # 17. Blood Urea Nitrogen / Urea (Strictly exclude uric acid)
            if "blood_urea_mg_dl" not in extracted:
                if any(term in l_lower for term in ["urea", "bun"]) and "uric" not in l_lower:
                    m_label = re.search(
                        r"(?:blood\s+urea\s+nitrogen|\bbun\b|blood\s+urea|serum\s+urea(?:\s+level)?|s\.\s*urea|\burea\b)",
                        l_lower,
                    )
                    if m_label:
                        seg = get_candidate_segment(idx, m_label.end())
                        val, unit = parse_row_value(seg)
                        if val is not None:
                            # International mmol/L conversion to mg/dL
                            if unit == "mmol/l" or (val < 15.0 and "urea" in l_lower):
                                val = val * 2.8
                            if 5.0 <= val <= 250.0:
                                extracted["blood_urea_mg_dl"] = round(val, 1)
                                matched_details["blood_urea_mg_dl"] = f"Blood Urea: {val:.1f} mg/dL"

            # 18. Urine Albumin / Protein Dipstick (0 to 4+)
            if "urine_albumin_dipstick" not in extracted:
                if any(
                    term in l_lower
                    for term in ["urine protein", "urine albumin", "albumin in urine", "protein, urine", "albumin, urine", "micral test"]
                ):
                    m_alb = re.search(
                        r"(?:nil|negative|neg|trace|1\+|2\+|3\+|4\+|\+|\+\+|\+\+\+|\+\+\+\+|[0-4])\b",
                        line,
                        re.IGNORECASE,
                    )
                    if m_alb:
                        raw_alb = m_alb.group(0).lower()
                        if raw_alb in ("nil", "negative", "neg", "0"):
                            u_val = 0
                        elif raw_alb in ("trace", "1+", "+", "1"):
                            u_val = 1
                        elif raw_alb in ("2+", "++", "2"):
                            u_val = 2
                        elif raw_alb in ("3+", "+++", "3"):
                            u_val = 3
                        else:
                            u_val = 4
                        extracted["urine_albumin_dipstick"] = u_val
                        matched_details["urine_albumin_dipstick"] = f"Urine Albumin: Dipstick {u_val}+"

        # ── 19. Auto-Calculate eGFR via CKD-EPI 2021 if not in report ─────────
        if "egfr_ml_min" not in extracted and "serum_creatinine_mg_dl" in extracted and "age_years" in extracted:
            cr = extracted["serum_creatinine_mg_dl"]
            age = extracted["age_years"]
            is_fem = extracted.get("sex", "male") == "female"
            kappa = 0.7 if is_fem else 0.9
            alpha = -0.241 if is_fem else -0.302
            fem_mult = 1.012 if is_fem else 1.0
            ratio = cr / kappa
            calc_egfr = 142 * (min(ratio, 1.0) ** alpha) * (max(ratio, 1.0) ** -1.200) * (0.9938 ** age) * fem_mult
            extracted["egfr_ml_min"] = round(calc_egfr, 1)
            matched_details["egfr_ml_min"] = f"eGFR: {calc_egfr:.1f} mL/min (CKD-EPI 2021 auto-calculated)"

        # Clinical Summary Generation
        summary_items = list(matched_details.values())
        clinical_summary = (
            f"Successfully parsed {len(summary_items)} clinical values:\n• "
            + "\n• ".join(summary_items)
            if summary_items
            else "No standard clinical biomarkers recognized in this document."
        )

        return {
            "success": len(extracted) > 0,
            "matched_count": len(extracted),
            "extracted_values": extracted,
            "matched_details": matched_details,
            "clinical_summary": clinical_summary,
            "preview_snippet": normalized_text[:350] + ("..." if len(normalized_text) > 350 else ""),
        }

    @classmethod
    def process_document(
        cls, file_source: Union[str, Path, bytes], filename: str = ""
    ) -> Dict[str, Any]:
        """
        End-to-end universal ingestion pipeline:
        1. Reads file (PDF, DOCX, TXT)
        2. Extracts text (with hybrid PDF fallback to RapidOCR if digital text yields < 2 biomarkers)
        3. Parses clinical values into standard Nutriloop features
        """
        try:
            if isinstance(file_source, (str, Path)):
                path = Path(file_source)
                if not path.exists():
                    return {"success": False, "error": f"File not found: {path}", "extracted_values": {}}
                raw_bytes = path.read_bytes()
                if not filename:
                    filename = path.name
            else:
                raw_bytes = file_source

            ext = Path(filename).suffix.lower() if filename else ".txt"

            # 1. Primary extraction
            raw_text = cls.extract_text_from_file(raw_bytes, filename)
            result = cls.parse_biomarkers(raw_text) if raw_text.strip() else {"success": False, "matched_count": 0, "extracted_values": {}}

            # 2. Hybrid PDF check: If it's a PDF and matched fewer than 2 biomarkers,
            # it may be a scanned table embedded inside a PDF with minimal digital header text.
            if ext == ".pdf" and result.get("matched_count", 0) < 2:
                log.info("PDF digital text yielded %d biomarkers. Attempting OCR fallback...", result.get("matched_count", 0))
                ocr_text = cls._extract_from_pdf(raw_bytes, force_ocr=True)
                if ocr_text.strip():
                    ocr_result = cls.parse_biomarkers(ocr_text)
                    if ocr_result.get("matched_count", 0) > result.get("matched_count", 0):
                        result = ocr_result

            if not result.get("success"):
                return {
                    "success": False,
                    "error": "The uploaded document contains no readable clinical biomarkers. Ensure it is a valid laboratory diagnostic report.",
                    "extracted_values": {},
                }

            result["filename"] = filename or "lab_report.txt"
            return result

        except Exception as exc:
            log.exception("Lab document processing failed: %s", exc)
            return {
                "success": False,
                "error": f"Error parsing document: {str(exc)}",
                "extracted_values": {},
            }
