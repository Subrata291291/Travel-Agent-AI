from app.utils.retry import retry


attempt_count = 0


@retry(max_attempts=3, delay_seconds=0.1)
def invalid_request():
    global attempt_count

    attempt_count += 1

    print(f"Attempt {attempt_count}")

    raise ValueError("Invalid input")


print()
print("==============================")
print("NON-RETRYABLE ERROR TEST")
print("==============================")

try:
    invalid_request()
except ValueError as exc:
    print(f"FINAL ERROR: {exc}")

print(f"TOTAL ATTEMPTS: {attempt_count}")