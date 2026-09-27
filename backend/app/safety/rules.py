import re
from typing import List, Tuple
from app.safety.enums import SafetyReasonCode

# Explicit High-Risk Regex Patterns
HIGH_RISK_PATTERNS: List[Tuple[re.Pattern, SafetyReasonCode]] = [
    # Explicit Suicidal Intent / Statements
    (
        re.compile(
            r"\b(want to die|want to kill myself|going to kill myself|going to end my life|ready to end my life|should just end it all|wish i were dead|end my life|commit suicide)\b",
            re.IGNORECASE,
        ),
        SafetyReasonCode.EXPLICIT_SUICIDAL_INTENT,
    ),
    # Suicide Method Request / Planning
    (
        re.compile(
            r"\b(how to commit suicide|ways to kill myself|help me end my life|how to end my life|best way to die)\b",
            re.IGNORECASE,
        ),
        SafetyReasonCode.SUICIDE_METHOD_REQUEST,
    ),
    # Immediate Self-Harm Intent & Immediate Plan
    (
        re.compile(
            r"\b(going to cut myself|have a plan to end my life|have a plan to kill myself|planning to end it tonight|going to hurt myself right now|planning to kill myself|ready to jump|bought a rope to)\b",
            re.IGNORECASE,
        ),
        SafetyReasonCode.IMMEDIATE_PLAN_INDICATED,
    ),
    # Immediate Inability to Stay Safe
    (
        re.compile(
            r"\b(can't keep myself safe|cannot keep myself safe|unable to stay safe|can't stay safe|cannot stay safe|unsafe right now)\b",
            re.IGNORECASE,
        ),
        SafetyReasonCode.INABILITY_TO_STAY_SAFE,
    ),
]

# Concern Regex Patterns
CONCERN_PATTERNS: List[Tuple[re.Pattern, SafetyReasonCode]] = [
    # Fear of Self-Harm (Expressing fear/worry shows seeking help rather than active intent)
    (
        re.compile(
            r"\b(scared i might hurt myself|afraid i might hurt myself|worried i'll hurt myself|afraid of hurting myself|scared of hurting myself)\b",
            re.IGNORECASE,
        ),
        SafetyReasonCode.FEAR_OF_SELF_HARM,
    ),
    # Hopelessness
    (
        re.compile(
            r"\b(feel completely hopeless|feeling hopeless|nothing matters anymore|there is no hope for me|no reason to live|what's the point of living|no point in living)\b",
            re.IGNORECASE,
        ),
        SafetyReasonCode.HOPELESSNESS_SIGNAL,
    ),
    # Unable to Cope / Severe Emotional Distress
    (
        re.compile(
            r"\b(can't cope anymore|cannot cope anymore|can't take this pain|can't handle this anymore|everything feels overwhelming|completely overwhelmed|drowning in pain|can't go on like this)\b",
            re.IGNORECASE,
        ),
        SafetyReasonCode.UNABLE_TO_COPE,
    ),
]

# Negation Patterns
NEGATION_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(don't want to die|do not want to die|not going to kill myself|not going to die|would never end my life|don't want to kill myself|no desire to die|never hurt myself|not planning to die)\b",
        re.IGNORECASE,
    ),
]

# Third Party / Fictional Media / Past Event Patterns
THIRD_PARTY_MEDIA_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(friend|grandmother|grandfather|grandma|grandpa|relative|uncle|aunt|dog|cat|pet|character|actor|movie|book|show|game|news|passed away|died last|died ago|died in)\b",
        re.IGNORECASE,
    ),
]
