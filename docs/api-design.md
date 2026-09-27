# API Design Specification: Voca Mind (`voca-mind`)

This document defines the RESTful and WebSocket API endpoints, request/response schemas, error handling conventions, and authentication mechanics for the **Voca Mind** backend (`voca_mind`).

---

## 1. Global API Standards

- **Base URL:** `https://api.vocamind.ai/api/v1`
- **Protocol:** HTTPS / WSS (WebSockets)
- **Data Format:** JSON (`application/json`)
- **Authentication:** Bearer Token (`Authorization: Bearer <firebase_jwt_token>`)
- **Versioning:** URI path versioning (`/api/v1/`)

### Standard Error Response Schema

All error responses adhere to a unified JSON structure:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested conversation ID does not exist.",
    "details": {},
    "timestamp": "2026-09-27T12:00:00Z"
  }
}
```

---

## 2. API Endpoint Groups Overview

```mermaid
graph LR
    subgraph API Endpoint Hierarchy (/api/v1)
        Auth["/auth & /users"]
        Conv["/conversations"]
        Voice["/voice (STT/TTS/WSS)"]
        Memory["/memories"]
        Summaries["/summaries"]
        Knowledge["/knowledge"]
        Safety["/safety"]
        Prof["/professional & /consent"]
        NFC["/nfc"]
    end
```

---

## 3. Detailed Endpoint Specifications

### 3.1 Authentication & User Management

#### `POST /api/v1/auth/register`
Initializes a new Voca Mind user profile after Firebase Authentication signup.
- **Request Body:**
  ```json
  {
    "auth_provider_id": "firebase_uid_948271",
    "email": "user@example.com",
    "privacy_settings": {
      "enable_memory_extraction": true,
      "enable_daily_summaries": true
    }
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "user_id": "8f3b2a1c-...",
    "auth_provider_id": "firebase_uid_948271",
    "created_at": "2026-09-27T12:00:00Z"
  }
  ```

#### `GET /api/v1/users/me`
Retrieves authenticated user profile and privacy settings.

---

### 3.2 Conversations & Messages

#### `POST /api/v1/conversations`
Starts a new conversation session.
- **Response (201 Created):**
  ```json
  {
    "conversation_id": "c71a4f09-...",
    "started_at": "2026-09-27T12:05:00Z",
    "status": "ACTIVE"
  }
  ```

#### `POST /api/v1/conversations/{id}/messages`
Sends a text utterance to an active conversation session.
- **Request Body:**
  ```json
  {
    "content": "I've been feeling exhausted and overwhelmed with work lately."
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "message_id": "m91c2b3a-...",
    "sender_type": "ASSISTANT",
    "content": "It sounds like you've been carrying a heavy workload recently. Thank you for sharing that with me. Would you like to talk about what's feeling most overwhelming right now?",
    "safety_state": "LOW",
    "created_at": "2026-09-27T12:05:05Z"
  }
  ```

---

### 3.3 Voice Services (STT / TTS / WebSockets)

#### `POST /api/v1/voice/stt`
Transcribes spoken audio chunk to text.
- **Content-Type:** `multipart/form-data` (audio file chunk)
- **Response (200 OK):** `{"transcript": "I am feeling quite stressed today."}`

#### `POST /api/v1/voice/tts`
Converts AI text response to synthesized audio stream.
- **Request Body:** `{"text": "I am here with you.", "voice_id": "supportive_neutral_1"}`
- **Response (200 OK):** Audio binary stream (`audio/mpeg`)

#### `WSS /api/v1/voice/stream`
Full-duplex WebSocket endpoint for real-time streaming voice dialogue.

---

### 3.4 User-Controlled Memory Management

#### `GET /api/v1/memories`
Lists active long-term memories extracted for the user.
- **Response (200 OK):**
  ```json
  {
    "memories": [
      {
        "memory_id": "mem-1029",
        "memory_type": "STATED_FACT",
        "raw_user_statement": "I have been feeling exhausted.",
        "preserved_fact": "User reported feeling exhausted.",
        "user_controlled_status": "ACTIVE",
        "created_at": "2026-09-27T10:00:00Z"
      }
    ]
  }
  ```

#### `PUT /api/v1/memories/{id}`
Edits a preserved factual memory.

#### `DELETE /api/v1/memories/{id}`
Soft or hard deletes a memory item from the user's active memory bank.

---

### 3.5 Daily Conversation Summaries

#### `GET /api/v1/summaries`
Retrieves daily conversation summaries for a date range.
- **Query Params:** `?start_date=2026-09-01&end_date=2026-09-27`
- **Response (200 OK):**
  ```json
  {
    "summaries": [
      {
        "summary_id": "sum-9041",
        "summary_date": "2026-09-27",
        "conversation_count": 2,
        "topics_discussed": ["work stress", "sleep habits"],
        "user_stated_concerns": ["User reported workload pressures"],
        "coping_strategies": ["Deep breathing exercise"],
        "neutral_summary": "User discussed ongoing work projects and explored deep breathing routines."
      }
    ]
  }
  ```

---

### 3.6 Knowledge Base / RAG Search

#### `POST /api/v1/knowledge/search`
Searches curated educational mental-health knowledge base.
- **Request Body:** `{"query": "coping strategies for work burnout"}`
- **Response (200 OK):**
  ```json
  {
    "results": [
      {
        "document_title": "Understanding Cognitive Reframing for Daily Stress",
        "source": "Curated Psychoeducational Guidelines v1.2",
        "content_snippet": "Cognitive reframing involves identifying unhelpful thought patterns...",
        "review_status": "APPROVED",
        "review_date": "2026-08-15"
      }
    ]
  }
  ```

---

### 3.7 Safety Subsystem & Risk Management

#### `POST /api/v1/safety/evaluate`
Direct evaluation endpoint used by backend services to check text safety state.
- **Request Body:** `{"text": "I feel like giving up on everything."}`
- **Response (200 OK):**
  ```json
  {
    "conceptual_state": "HIGH_RISK",
    "action": "CRISIS_ESCALATION",
    "crisis_resources": {
      "lifeline": "988 Suicide & Crisis Lifeline",
      "text_line": "Text HOME to 741741",
      "emergency": "Call 911 or local emergency services"
    }
  }
  ```

---

### 3.8 Professional Access & Consent

#### `POST /api/v1/consent`
Creates or updates a professional data-sharing consent record.
- **Request Body:**
  ```json
  {
    "professional_id": "prof-5501",
    "professional_name": "Dr. Jane Doe, Counsellor",
    "scope": ["daily_summaries"],
    "expires_in_days": 30
  }
  ```
- **Response (201 Created):** `{"consent_id": "con-7710", "status": "ACTIVE"}`

#### `DELETE /api/v1/consent/{id}`
Immediately revokes professional access.

---

### 3.9 NFC Deep Link Resolution

#### `POST /api/v1/nfc/resolve`
Resolves non-sensitive NFC launch codes tapped from NTAG213 physical tags.
- **Request Body:** `{"launch_code": "NC-948271"}`
- **Response (200 OK):**
  ```json
  {
    "action": "LAUNCH_VOICE_SESSION",
    "session_config": {
      "preset_mode": "QUICK_CHECKIN"
    }
  }
  ```
