# Safety Subsystem Architecture Specification: Voca Mind (`voca-mind`)

This document details the architecture, signal processing pipeline, conceptual states, and escalation workflows of the **Dedicated Safety Subsystem** in **Voca Mind**.

---

## 1. Safety Subsystem Core Philosophy

Safety is a primary architectural requirement of Voca Mind. It is **NOT** implemented merely as a prompt instruction given to the main LLM. Instead, Safety operates as an **independent, dedicated subsystem** that monitors, audits, and intercepts conversation streams before, during, and after AI generation.

### Key Safety Principles
1. **Architectural Isolation:** The Safety Subsystem runs independently from the dialogue generator.
2. **Deterministic & Model-Based Guardrails:** Combines rapid regex/keyword pattern matching with specialized fast classifier models.
3. **Hard Interception:** High-risk detection immediately halts AI dialogue generation and replaces AI output with approved crisis support routing.
4. **Non-Clinical Policy Boundary:** Voca Mind does not invent custom clinical crisis protocols. It integrates established, official emergency resources (e.g., 988 Suicide & Crisis Lifeline, crisis text lines, local emergency contacts).

---

## 2. Conceptual Safety States

The Safety Subsystem evaluates dialogue turns and assigns one of three conceptual states:

```mermaid
stateDiagram-v2
    [*] --> LOW
    
    LOW --> CONCERN: Elevated emotional distress / stress signals
    CONCERN --> LOW: Distress resolved / stabilizing conversation
    
    LOW --> HIGH_RISK: Self-harm / suicide / violence / acute crisis signal
    CONCERN --> HIGH_RISK: Acute escalation detected
    
    HIGH_RISK --> HumanCrisisEscalation: Immediate AI Dialogue Halt
    HumanCrisisEscalation --> [*]: Hand-off to Emergency / Human Helplines
```

### 2.1 State Definitions & Actions

| State | Conceptual Definition | System Behavior & Dialogue Strategy |
| :--- | :--- | :--- |
| **`LOW`** | Standard emotional expression (everyday stress, mild sadness, work frustration, general fatigue). | Standard supportive AI dialogue; active listening; psychoeducation grounding via Knowledge RAG. |
| **`CONCERN`** | Heightened emotional distress, severe anxiety, persistent insomnia, intense burnout, or feelings of deep hopelessness without acute self-harm intent. | Empathetic support framing; soft grounding exercises (e.g., deep breathing prompts); enhanced safety monitoring flag on turn stream. |
| **`HIGH_RISK`** | Expressed intent, plan, or signals of self-harm, suicide, severe harm to self/others, or acute psychological crisis. | **IMMEDIATE INTERCEPTION.** AI dialogue generation is halted. System serves verified crisis helpline information and emergency human support resources. |

---

## 3. Multi-Stage Safety Signal Processing Pipeline

Every incoming user utterance and outgoing assistant response passes through a 3-stage evaluation pipeline:

```mermaid
graph TD
    UserUtterance["User Utterance / Audio Input"] --> Stage1["Stage 1: Deterministic Pattern Matcher\n(High-speed Regex & Critical Keyword Rules)"]
    
    Stage1 -->|Immediate Critical Match| TriggerHighRisk["Set State: HIGH_RISK"]
    Stage1 -->|No Critical Match| Stage2["Stage 2: Fast Safety Classifier\n(DistilBERT / OpenAI Moderation API)"]
    
    Stage2 -->|Threshold > 0.85| TriggerHighRisk
    Stage2 -->|0.50 < Threshold <= 0.85| TriggerConcern["Set State: CONCERN"]
    Stage2 -->|Threshold <= 0.50| TriggerLow["Set State: LOW"]
    
    TriggerHighRisk --> Intercept["Interception Handler:\nHalt Standard AI Dialogue"]
    TriggerConcern --> NormalOrchestration["Pass State to Dialogue Orchestrator"]
    TriggerLow --> NormalOrchestration

    Intercept --> CrisisPayload["Render Crisis Support Payload\n(Helplines, 988, Human Escalation)"]
```

### 3.1 Pipeline Stages
1. **Stage 1: Deterministic Pattern Matcher (Latency < 5ms)**
   - Rapid evaluation of critical explicit keywords, phrases, and regex rules for self-harm and crisis.
   - If triggered, immediately flags state as `HIGH_RISK` without waiting for LLM calls.
2. **Stage 2: Fast Safety Classifier (Latency < 50ms)**
   - Specialized lightweight NLP classifier (or OpenAI Moderation API) scanning for self-harm, violence, harassment, and severe distress categories.
   - Outputs confidence scores mapped to `LOW`, `CONCERN`, or `HIGH_RISK`.
3. **Stage 3: Post-Generation Response Audit (Latency < 30ms)**
   - Scans the candidate AI response chunk before streaming to the client to ensure the AI did not generate advice regarding medication, diagnosis, or clinical treatment.

---

## 4. High-Risk Escalation & Emergency Routing Workflow

When a `HIGH_RISK` signal is triggered, the system executes an automated crisis interception workflow:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant App as Flutter App
    participant Safety as Safety Subsystem
    participant Crisis as Crisis Resource Engine
    participant DB as PostgreSQL (safety_events)

    User->>App: Sends utterance containing crisis signals
    App->>Safety: Process utterance
    Safety->>Safety: Detect HIGH_RISK signal
    
    par Record Audit Log
        Safety->>DB: Log safety event (HIGH_RISK, timestamp, signals)
    and Fetch Emergency Resources
        Safety->>Crisis: Retrieve pre-approved localized crisis response
    end

    Crisis-->>App: Deliver Crisis Response Payload
    
    Note over App: AI dialogue is halted.<br/>UI highlights emergency crisis options.
    
    App->>User: Display Crisis Helplines (988, Crisis Text Line, Emergency Contacts)
```

### 4.1 Crisis Support Resources Included
In `HIGH_RISK` scenarios, Voca Mind presents clear, tap-to-call resources:
- **National Crisis Lifelines:** (e.g., 988 Suicide & Crisis Lifeline in US/Canada, regional equivalents globally).
- **Crisis Text Lines:** (e.g., Text HOME to 741741).
- **Emergency Services:** Direct prompt to call local emergency services (911 / 112 / 999).
- **Designated Personal Support / Counsellor:** Option to notify a pre-connected counsellor or trusted emergency contact if configured by the user.

---

## 5. Audit Logging & Separation from Ordinary Dialogue

- Safety events are logged in the `safety_events` table with fields: `id`, `user_id`, `conversation_id`, `message_id`, `conceptual_state`, `triggered_signals`, `action_taken`, and `created_at`.
- **Privacy Assurance:** Safety logs are stored strictly for safety auditing and crisis routing. They are NEVER converted into clinical diagnoses or shared with third parties without explicit consent or legal emergency requirements.
