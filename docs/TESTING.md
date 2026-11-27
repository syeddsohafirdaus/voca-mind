# Voca Mind Testing

## Backend

Run:

    python -m pytest -q --tb=short

Coverage includes:

- Authentication and role restrictions
- Conversation orchestration
- AI safety routing
- Professional verification
- Professional assignments
- Professional messaging
- Support requests
- Human takeover
- Notifications
- Guardian authorization
- Wellbeing sharing
- Consent validation
- Stale consent protection

## Frontend

Run:

    flutter analyze
    flutter test
    flutter build apk --debug

Automated frontend tests include:

- Professional consent dialogs
- Support-offer parsing
- Rejection of invalid support offers
- Rejection of automatic notification claims
- Rejection of unsupported emergency service claims

## Integration Checks

- Backend health endpoint
- API module registration
- Unauthorized endpoint access
- PostgreSQL migration consistency
- Flutter application installation
- Source-level frontend feature connections

## Remaining Verification

Full authenticated mobile workflows, real PostgreSQL concurrency,
production security, clinical effectiveness, and operational
professional availability require further validation.
