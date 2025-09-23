# path: backend/rules/regex_en.py
from __future__ import annotations

import re
from typing import Dict, List


# Deterministic patterns for HPI/exam/risks extraction (English)
RE_CC = re.compile(r"\b(chest pain|seizure|fever|shortness of breath|sob|abdominal pain|headache)\b", re.I)
RE_ONSET = re.compile(r"\b(since|for)\s+(\d+\s*(?:min(?:ute)?s?|hr(?:s)?|hour(?:s)?|day(?:s)?|week(?:s)?))\b", re.I)
RE_QUALITY = re.compile(r"\b(sharp|dull|pressure|burning|throbbing|stabbing|tight)\b", re.I)
RE_ASSOC = re.compile(r"\b(nausea|vomit(?:ing)?|diaphoresis|sweat(?:ing)?|dyspnea|palpitations|photophobia)\b", re.I)
RE_RED = re.compile(r"\b(syncope|hemoptysis|hypotension|stemi|stroke|focal weakness)\b", re.I)
RE_MOD = re.compile(r"\b(worse with|better with|relieved by|exacerbated by)\s+([\w\s]+?)(?:[.;]|$)", re.I)
RE_EXAM_CV = re.compile(r"\b(regular rate and rhythm|murmur|tachycardia|bradycardia|normal s1 s2)\b", re.I)
RE_EXAM_LUNGS = re.compile(r"\b(clear to auscultation|wheez(es|ing)?|crackles|rales|rhonchi)\b", re.I)


def extract(text: str) -> Dict:
    """
    Deterministic extraction from a text span.
    Returns a partial VisitJSON-shaped dict.
    """
    t = (text or "").strip()
    out = {
        "chief_complaint": None,
        "hpi": {"onset": None, "quality": None, "modifiers": [], "associated_symptoms": [], "red_flags": []},
        "exam_bits": {"cv": None, "lungs": None},
        "risks": [],
    }

    m = RE_CC.search(t)
    if m:
        out["chief_complaint"] = m.group(1).lower()

    mo = RE_ONSET.search(t)
    if mo:
        out["hpi"]["onset"] = mo.group(0)

    mq = RE_QUALITY.search(t)
    if mq:
        out["hpi"]["quality"] = mq.group(1).lower()

    out["hpi"]["associated_symptoms"] = list({m.group(1).lower() for m in RE_ASSOC.finditer(t)})
    out["hpi"]["red_flags"] = list({m.group(1).lower() for m in RE_RED.finditer(t)})
    out["hpi"]["modifiers"] = [m.group(0).strip().lower() for m in RE_MOD.finditer(t)]

    ecv = RE_EXAM_CV.search(t)
    if ecv:
        out["exam_bits"]["cv"] = ecv.group(1).lower()

    el = RE_EXAM_LUNGS.search(t)
    if el:
        out["exam_bits"]["lungs"] = el.group(1).lower()

    return out
