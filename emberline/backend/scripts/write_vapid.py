"""One-shot VAPID writer. Prints only the public key length."""
from __future__ import annotations

import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid


def main() -> None:
    dest = Path(sys.argv[1])
    v = Vapid()
    v.generate_keys()
    raw_pub = v.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public = base64.urlsafe_b64encode(raw_pub).rstrip(b"=").decode()
    pem = v.private_pem()
    if isinstance(pem, bytes):
        pem = pem.decode()
    escaped = pem.replace("\n", "\\n")
    dest.write_text(f"VAPID_PUBLIC_KEY={public}\nVAPID_PRIVATE_KEY={escaped}\n")
    dest.chmod(0o600)
    print(f"wrote {dest} public_len={len(public)}")


if __name__ == "__main__":
    main()
