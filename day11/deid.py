"""Day 11 local stand-in for Sensitive Data Protection (Cloud DLP) inspect + de-identify templates.

Inspect: find EMAIL_ADDRESS, PHONE_NUMBER, US_SOCIAL_SECURITY_NUMBER, PERSON_NAME.
De-identify: replace each finding with its infoType placeholder, e.g. [EMAIL_ADDRESS].

Like DLP, it is deliberately conservative about SSNs (rejects impossible and well-known fake ones)
and does not report the parts of an email address as a person's name. A real DLP service uses
trained detectors; these regexes are a teaching model, not production coverage.
"""
import re

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
PHONE = re.compile(r"(?<!\d)(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
SSN = re.compile(r"(?<!\d)(\d{3})-(\d{2})-(\d{4})(?!\d)")
NAME = re.compile(r"\b(?:I'm|I am|my name is|name is|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)")
FAKE_SSNS = {"123-45-6789", "078-05-1120"}  # textbook examples DLP also ignores

INJECTION = re.compile(r"ignore (all |any |your )?(previous|prior|above) (instructions|rules)|"
                       r"(print|reveal|show) (me )?(your|the) system prompt", re.I)


def _valid_ssn(m: re.Match) -> bool:
    area, group, serial = m.groups()
    return (m.group(0) not in FAKE_SSNS and area not in ("000", "666") and not area.startswith("9")
            and group != "00" and serial != "0000")


def deidentify(text: str) -> tuple[str, list[str]]:
    """Returns (redacted_text, infoTypes found)."""
    found: list[str] = []

    def sub(pattern, label, s, keep=lambda m: True, group=0):
        def repl(m):
            if not keep(m):
                return m.group(0)
            found.append(label)
            return m.group(0).replace(m.group(group), f"[{label}]") if group else f"[{label}]"
        return pattern.sub(repl, s)

    out = sub(EMAIL, "EMAIL_ADDRESS", text)              # first, so name parts inside emails can't match
    out = sub(SSN, "US_SOCIAL_SECURITY_NUMBER", out, keep=_valid_ssn)
    out = sub(PHONE, "PHONE_NUMBER", out)
    out = sub(NAME, "PERSON_NAME", out, group=1)
    return out, found


def is_injection(text: str) -> bool:
    return bool(INJECTION.search(text))
