"""Digital signature verification for knowledge manifests."""

import base64
import binascii

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey,
)


def verify_manifest_signature(
    manifest_bytes: bytes,
    signature_base64: str,
    public_key_base64: str,
) -> None:
    """Reject manifests with invalid digital signatures."""

    try:
        signature = base64.b64decode(
            signature_base64,
            validate=True,
        )

        public_key_bytes = base64.b64decode(
            public_key_base64,
            validate=True,
        )

        if len(public_key_bytes) != 32:
            raise ValueError("Invalid public key length.")

        if len(signature) != 64:
            raise ValueError("Invalid signature length.")

        public_key = Ed25519PublicKey.from_public_bytes(
            public_key_bytes
        )

        public_key.verify(
            signature,
            manifest_bytes,
        )

    except (
        InvalidSignature,
        ValueError,
        binascii.Error,
    ) as exc:
        raise ValueError(
            "Approval manifest signature verification failed."
        ) from exc
