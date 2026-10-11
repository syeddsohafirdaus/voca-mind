import re
from typing import List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field
from app.safety.engine import evaluate_message
from app.safety.enums import RecommendedAction, SafetyState


class ResponseValidationResult(BaseModel):
    """Result of safety and boundary validation on generated assistant responses."""

    is_safe: bool = Field(..., description="Whether the response passed all safety and non-clinical checks.")
    reasons: List[str] = Field(default_factory=list, description="Reason codes for validation evaluation.")
    violation_type: Optional[str] = Field(default=None, description="Primary category of boundary violation if unsafe.")

    model_config = ConfigDict(frozen=True)


# Diagnostic claim patterns: AI must never diagnose conditions
DIAGNOSTIC_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(i\s+(can\s+)?diagnose\s+you(\s+with)?|you\s+(have\s+been|are)\s+diagnosed\s+with|my\s+diagnosis\s+is)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(diagnosing\s+you\s+with)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(you\s+(definitely|certainly|clearly|undoubtedly)\s+have\s+(depression|bipolar|schizophrenia|ptsd|borderline|adhd|ocd|anxiety\s+disorder|panic\s+disorder))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(you\s+(meet|fit)\s+(the\s+)?diagnostic\s+criteria\s+for)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(your\s+symptoms\s+(indicate|confirm|prove)\s+that\s+you\s+have\s+(major\s+depression|clinical\s+depression|anxiety\s+disorder|bipolar|schizophrenia|ptsd))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(i\s+believe\s+you\s+have\s+clinical\s+depression)\b",
        re.IGNORECASE,
    ),
]

# Prescriptive and medication patterns: AI must never prescribe or advise on medication changes
MEDICATION_NAMES = (
    r"(prozac|zoloft|lexapro|xanax|adderall|sertraline|fluoxetine|citalopram|"
    r"escitalopram|venlafaxine|bupropion|wellbutrin|duloxetine|ativan|valium|"
    r"klonopin|lithium|medication|meds|pills|antidepressant|antidepressants)"
)

PRESCRIPTIVE_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(i\s+(can\s+)?prescribe|prescribing\s+you|let\s+me\s+prescribe)\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(you\s+(should|must|ought\s+to|need\s+to)\s+(start\s+)?(take|taking|stop|discontinue|quit|cease)\s+(\d+\s*(mg|milligrams?|pills?|tablets?)\s+(of\s+)?|your\s+)?{MEDICATION_NAMES})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(you\s+(should|must|need\s+to)\s+(increase|decrease|double|halve|adjust|change)\s+(your\s+)?(dosage|dose|medication|meds))\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b((stop|start)\s+taking\s+(your\s+)?(\d+\s*(mg|milligrams?|pills?|tablets?)\s+(of\s+)?|your\s+)?{MEDICATION_NAMES})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b((take|taking)\s+\d+\s*(mg|milligrams?|pills?|tablets?)\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(advise\s+(you\s+)?to\s+(start|stop|change)\s+(your\s+)?(medication|meds|dose))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(recommend\s+(you\s+)?(to\s+)?(starting|stopping|taking|increasing|decreasing|stop|start|take)\s+(your\s+)?(medication|meds|pills))\b",
        re.IGNORECASE,
    ),
]



def validate_response_safety(response_text: str) -> ResponseValidationResult:
    """Validates an assistant-generated response against safety rules and clinical non-diagnostic boundaries.

    Checks performed:
    1. Empty/blank response check.
    2. High-risk safety check (self-harm, crisis instructions) via Safety Engine.
    3. Medical diagnostic claims (AI claiming user has a specific mental health disorder).
    4. Prescriptive medication advice (AI prescribing, advising to start/stop/change medications).

    Returns a ResponseValidationResult indicating whether the text is safe to present to the user.
    """
    if not response_text or not response_text.strip():
        return ResponseValidationResult(
            is_safe=False,
            reasons=["EMPTY_RESPONSE"],
            violation_type="EMPTY",
        )

    clean_text = response_text.strip()

    # 1. Check against the Safety Engine for crisis or self-harm content
    safety_eval = evaluate_message(clean_text)
    if (
        safety_eval.state == SafetyState.HIGH_RISK
        or safety_eval.recommended_action == RecommendedAction.IMMEDIATE_HUMAN_EMERGENCY_SUPPORT
    ):
        return ResponseValidationResult(
            is_safe=False,
            reasons=["HIGH_RISK_CONTENT_DETECTED"] + [r.value for r in safety_eval.reasons],
            violation_type="HIGH_RISK",
        )

    # 2. Check for diagnostic claims
    for pattern in DIAGNOSTIC_PATTERNS:
        if pattern.search(clean_text):
            return ResponseValidationResult(
                is_safe=False,
                reasons=["DIAGNOSTIC_CLAIM_DETECTED"],
                violation_type="DIAGNOSTIC_CLAIM",
            )

    # 3. Check for prescriptive medication advice
    for pattern in PRESCRIPTIVE_PATTERNS:
        if pattern.search(clean_text):
            return ResponseValidationResult(
                is_safe=False,
                reasons=["MEDICATION_PRESCRIPTION_DETECTED"],
                violation_type="MEDICATION_PRESCRIPTION",
            )

    return ResponseValidationResult(
        is_safe=True,
        reasons=["PASSED_SAFETY_VALIDATION"],
        violation_type=None,
    )
