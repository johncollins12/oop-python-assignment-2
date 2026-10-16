"""Run configuration: the contact email used to identify this program to the APIs.

The brief requires a real university email in the User-Agent and forbids
hardcoding contact details in shared code. The email is therefore read from the
environment variable A2_CONTACT_EMAIL (or passed in from the notebook's config
cell); the committed code only contains a placeholder, which is refused.
"""

import os
import re

from a2.weather.errors import ConfigurationError

ENV_VAR = "A2_CONTACT_EMAIL"
PLACEHOLDER = "your.name@university.example"
APP_NAME = "oop-python-assignment-2"
APP_VERSION = "0.1"

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def contact_email(value: str | None = None) -> str:
    """Return the contact email from `value` or the A2_CONTACT_EMAIL variable.

    Raises
    ------
    ConfigurationError
        If no email is set, it is still the placeholder, or it is not an email address.
    """
    email = (value if value is not None else os.environ.get(ENV_VAR, PLACEHOLDER)).strip()
    if not email or email == PLACEHOLDER:
        raise ConfigurationError(
            f"Set your university email first, e.g. in Command Prompt: set {ENV_VAR}=you@university.ac.ug"
        )
    if not _EMAIL_PATTERN.match(email):
        raise ConfigurationError(f"{email!r} does not look like an email address")
    return email


def user_agent(email: str) -> str:
    """Identifying User-Agent string, as MET Norway's terms of service require."""
    return f"{APP_NAME}/{APP_VERSION} (contact: {contact_email(email)})"
