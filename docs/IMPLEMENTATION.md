# Voca Mind

## Project Overview

Voca Mind is an AI-powered emotional support companion designed
for adults aged 18–30.

The application provides a listening-first conversational
experience, voice interaction, optional guardian involvement,
and consent-based access to platform-verified professionals.

Voca Mind is a development prototype, not a replacement for
medical care, psychotherapy, or emergency services.

## Technology Stack

| Component | Technology |
|---|---|
| Mobile application | Flutter and Dart |
| Backend | FastAPI and Python |
| Authentication | Firebase Authentication |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Database migrations | Alembic |
| AI generation | Ollama / Qwen |
| Embeddings | Nomic Embed Text |
| Vector database | Qdrant |
| Speech recognition | Speech-to-text |
| Voice output | Flutter TTS |
| Version control | Git and GitHub |

## System Architecture

Flutter Mobile Application
        |
Firebase Authentication
        |
FastAPI REST API
        |
        +-- Authentication and role authorization
        +-- Conversation orchestration
        +-- Safety routing
        +-- Professional support management
        +-- Guardian authorization
        +-- Notification management
        |
        +-- PostgreSQL
        +-- Ollama
        +-- Qdrant

## User Roles

### Client

- AI conversation
- Conversation history
- Voice input and output
- Professional support requests
- Professional messaging
- Consent-based human takeover
- Optional guardian authorization
- Explicit wellbeing sharing
- Account and voice settings

### Professional

- Credential application
- Platform approval requirement
- Professional dashboard
- Assigned client management
- Professional messaging
- Consent-based takeover acceptance
- In-app notifications

### Guardian

- Client-authorized access
- Explicitly shared wellbeing updates
- Privacy-preserving dashboard
- No access to private AI conversations

### Platform Administration

- Professional application review
- Credential approval and rejection
- Professional suspension
- Eligible professional management
- Support request review
- Professional assignment proposals

Administrative operations require authorized platform access.

## AI Safety

The prototype includes safety-aware conversation routing,
high-risk response handling, professional support suggestions,
and output safety checks.

Professional support suggestions require explicit client consent.

The application does not automatically forward private AI
conversations to professionals or guardians.

Human takeover represents an accepted professional support
session, not guaranteed live monitoring or emergency intervention.

## Privacy Controls

- Firebase identity verification
- Backend role-based authorization
- Assignment-based professional access
- Explicit guardian authorization
- Revocable guardian access
- Versioned guardian consent
- Explicit wellbeing sharing
- Separate professional and AI conversations
- Strict consent validation
- Protected administrative endpoints

These controls are prototype implementations and have not
undergone independent production security certification.

## Knowledge Retrieval

The retrieval architecture uses embeddings and Qdrant.

Knowledge approval uses signed manifests and document hashes.

A clinically reviewed production knowledge corpus must be
prepared and approved before clinical deployment.

## Development Environment

Backend:
- Python virtual environment
- PostgreSQL
- Firebase Admin configuration
- Ollama
- Qdrant

Frontend:
- Flutter SDK
- Android SDK
- Android emulator
- Firebase client configuration

The Android emulator uses the development backend address:

http://10.0.2.2:8000/api/v1

This local HTTP configuration must be replaced with a secure
HTTPS deployment before production use.

## Running the Backend

From the backend directory:

    source ~/.venvs/voca-mind/bin/activate
    sudo service postgresql start
    python -m alembic upgrade head
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

API documentation:

    http://localhost:8000/docs

Health endpoint:

    http://localhost:8000/api/v1/health

## Running the Frontend

From the frontend directory:

    flutter pub get
    flutter run -d emulator-5554

Debug APK:

    flutter build apk --debug

## Verification

Backend regression tests:

    python -m pytest -q --tb=short

Database schema verification:

    python -m alembic check

Flutter verification:

    flutter analyze
    flutter test

The project includes automated backend tests, consent validation
tests, Flutter widget tests, and support-offer parsing tests.

Successful compilation and automated tests do not establish
complete authenticated mobile workflow coverage.

## Current Limitations

- Independent clinical validation is pending.
- Production penetration testing is pending.
- Complete authenticated mobile end-to-end coverage is pending.
- Professional identity verification requires human administration.
- Professional availability is not guaranteed in real time.
- Notifications are in-app rather than emergency dispatch.
- Production data retention and deletion policies require review.
- Guardian identity pairing requires further hardening.
- Production deployment requires HTTPS and secret management.
- A clinically reviewed knowledge corpus is required.

## Deployment Status

Local engineering prototype.

Not approved for unsupervised clinical use or real-world
emergency response.
