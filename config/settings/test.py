from .dev import *  # noqa: F401,F403

# Fast, insecure hasher: for automated tests only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
