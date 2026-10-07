import bcrypt


def hash_password(password: str) -> str:
    """
    Convert a plain-text password into a secure bcrypt hash.

    Role:
    - Used when creating a user password.
    - Used when changing a password.
    - The plain password is never stored in the database.

    Example:
        password = "MySecret123"

        stored value:
            $2b$12$...
    """

    if not password:
        raise ValueError("Password cannot be empty.")

    password_bytes = password.encode("utf-8")

    password_hash = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(),
    )

    return password_hash.decode("utf-8")


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.

    Role:
    - Used during login.
    - Returns True when the password is correct.
    - Returns False when the password is incorrect.
    """

    if not password or not password_hash:
        return False

    password_bytes = password.encode("utf-8")
    hash_bytes = password_hash.encode("utf-8")

    return bcrypt.checkpw(
        password_bytes,
        hash_bytes,
    )