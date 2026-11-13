import base64
import hashlib
import hmac
import os

SCRYPT_COST = 2**14
SCRYPT_BLOCK_SIZE = 8
SCRYPT_PARALLELIZATION = 1
SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = os.urandom(SALT_BYTES)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_COST,
        r=SCRYPT_BLOCK_SIZE,
        p=SCRYPT_PARALLELIZATION,
    )
    encoded_salt = base64.urlsafe_b64encode(salt).decode("ascii")
    encoded_key = base64.urlsafe_b64encode(derived_key).decode("ascii")
    return (
        f"scrypt${SCRYPT_COST}${SCRYPT_BLOCK_SIZE}${SCRYPT_PARALLELIZATION}"
        f"${encoded_salt}${encoded_key}"
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, cost, block_size, parallelization, encoded_salt, encoded_key = (
            encoded_hash.split("$")
        )
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
        expected_key = base64.urlsafe_b64decode(encoded_key.encode("ascii"))
        actual_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(cost),
            r=int(block_size),
            p=int(parallelization),
        )
        return hmac.compare_digest(actual_key, expected_key)
    except (ValueError, TypeError):
        return False
