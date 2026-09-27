import os
from typing import Any, Dict
import firebase_admin
from firebase_admin import auth, credentials
from app.config import settings
from app.logger import logger


def init_firebase() -> None:
    """Initializes the Firebase Admin SDK if not already initialized.
    
    Credentials MUST come from environment variables or secure local paths.
    NEVER hardcode keys or service-account JSON contents in source code.
    """
    if firebase_admin._apps:
        return

    # Check for custom emulator setting
    if settings.FIREBASE_AUTH_EMULATOR_HOST:
        os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = settings.FIREBASE_AUTH_EMULATOR_HOST

    try:
        if settings.FIREBASE_CREDENTIALS_PATH and os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized with certificate file.")
        elif settings.FIREBASE_PROJECT_ID:
            options = {"projectId": settings.FIREBASE_PROJECT_ID}
            firebase_admin.initialize_app(options=options)
            logger.info("Firebase Admin SDK initialized with project ID.")
        else:
            # Fallback to default application credentials or uninitialized placeholder
            firebase_admin.initialize_app()
            logger.info("Firebase Admin SDK initialized with default application credentials.")
    except Exception as e:
        logger.warning(f"Firebase Admin SDK initialization deferred or warning: {str(e)}")


def verify_firebase_id_token(token: str) -> Dict[str, Any]:
    """Verifies a Firebase ID token using the Firebase Admin SDK.
    
    Returns the decoded token claims dictionary containing 'uid'.
    Raises ValueError if the token is invalid or verification fails.
    NEVER logs the token or raw credentials.
    """
    init_firebase()
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        # Raise generic ValueError without exposing detailed verification stack traces
        raise ValueError("Token verification failed") from e
