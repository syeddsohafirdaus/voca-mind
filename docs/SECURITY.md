# Voca Mind Security Guidelines

## Credential Management

Never commit:

- Backend .env files
- Firebase Admin service account credentials
- Private signing keys
- OpenAI secret API keys
- Database passwords
- Database backups
- Android release signing credentials
- Authentication tokens
- Private conversation exports

Use environment variables and protected local configuration.

Firebase client configuration is distinct from Firebase Admin
credentials. Client API keys should have appropriate restrictions.

## Access Control

All protected operations must enforce authorization on the
backend, regardless of frontend restrictions.

Professional access requires an active verified account and
an eligible assignment.

Guardian access requires explicit active client authorization.

Administrative access requires an authorized platform identity.

## Consent

Consent must be explicit and validated by the backend.

Guardian wellbeing sharing must respect the current consent
version and authorization status.

Private AI conversations must not be automatically shared.

## Incident Response

If a secret is accidentally committed:

1. Revoke or rotate the credential.
2. Investigate its usage.
3. Remove it from affected repository history where appropriate.
4. Review access logs and affected systems.

Removing a secret from the latest commit alone is insufficient.

## Production Requirements

Before production deployment:

- Enforce HTTPS.
- Complete independent security testing.
- Establish clinical review procedures.
- Implement data retention and deletion policies.
- Review applicable privacy regulations.
- Establish professional verification procedures.
- Establish incident response procedures.
- Validate crisis-response information.
- Test authenticated mobile workflows.
- Review database concurrency and consent revocation.
- Configure secure monitoring without exposing private messages.
