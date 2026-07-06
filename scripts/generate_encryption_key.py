#!/usr/bin/env python
"""Generate a Fernet key for the ENCRYPTION_KEY environment variable."""

from cryptography.fernet import Fernet


def main() -> None:
    key = Fernet.generate_key().decode("utf-8")
    print(f"ENCRYPTION_KEY={key}")


if __name__ == "__main__":
    main()
