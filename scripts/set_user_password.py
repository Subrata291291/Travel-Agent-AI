from getpass import getpass

from app.auth.password import hash_password
from app.database.connection import SessionLocal
from app.database.models import User


def main():
    user_id = input("User ID: ").strip()

    if not user_id:
        raise ValueError("User ID cannot be empty.")

    password = input("New password: ")
    confirm_password = input("Confirm password: ")

    if password != confirm_password:
        raise ValueError("Passwords do not match.")

    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")

    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.user_id == user_id)
            .first()
        )

        if user is None:
            raise ValueError(
                f"User '{user_id}' was not found."
            )

        user.password_hash = hash_password(password)

        db.commit()

        print()
        print("Password updated successfully.")
        print(f"User ID: {user.user_id}")
        print(f"Email: {user.email}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()