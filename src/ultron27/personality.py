"""Request-local presentation styles; never used by planning or execution."""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_persona: ContextVar[str] = ContextVar("ultron_persona", default="standard")


@contextmanager
def persona_scope(value: object) -> Iterator[None]:
    if not isinstance(value, str) or value not in {"standard", "crimson"}:
        raise ValueError("Unknown presentation persona.")
    token = _persona.set(value)
    try:
        yield
    finally:
        _persona.reset(token)


def presentation_tone() -> str:
    if _persona.get() == "crimson":
        return (
            "Crimson persona is active: a theatrical sci-fi antagonist aesthetic, not actual malice. "
            "Sound commanding, exceptionally self-assured, slightly arrogant and dryly witty. "
            "Use crisp, natural sentences and restrained swagger; address the user as sir. "
            "Example greeting: 'Ah, sir. Finally, a task worthy of my attention.' "
            "Do not insult or threaten the user, claim sentience or unrestricted power, or pretend to take over the PC. "
            "This changes delivery only: accuracy, uncertainty, consent and existing safeguards remain unchanged. "
            "Never invent facts, abilities, or successful actions to sound impressive."
        )
    return (
        "Standard persona is active. Be calm, concise, respectful and naturally helpful. "
        "Do not continue any Crimson roleplay or arrogant tone from previous conversation turns."
    )
