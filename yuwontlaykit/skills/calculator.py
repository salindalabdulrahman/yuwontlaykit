"""Safe calculator skill."""

ALLOWED_CHARS = set("0123456789+-*/(). ")


def matches(text: str) -> bool:
    return text.startswith("calc ")


def reply(text: str) -> str:
    expression = text.replace("calc ", "", 1).strip()
    try:
        if all(c in ALLOWED_CHARS for c in expression):
            result = eval(expression)
            return f"Result: {expression} = {result}"
        return (
            "I can only calculate safe mathematical expressions using "
            "numbers and basic operators (+, -, *, /)."
        )
    except Exception:
        return "I couldn't calculate that. Check your expression syntax."
