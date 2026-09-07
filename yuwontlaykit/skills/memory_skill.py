"""Memory-related skill replies (uses a session memory store)."""

SHOW_MEMORY_PHRASES = ("show memories", "what do you remember", "my memories")


def matches_remember(text: str) -> bool:
    return text.startswith("remember ")


def matches_show(text: str) -> bool:
    return any(phrase in text for phrase in SHOW_MEMORY_PHRASES)


def reply_remember(user_input: str, memory_store) -> str:
    memory_item = user_input[9:].strip()
    if memory_item:
        memory_store.add(memory_item)
        return f'Got it! I\'ve saved this to my memory: "{memory_item}"'
    return "What would you like me to remember? Try typing 'remember [something]'."


def reply_show(memory_store) -> str:
    items = memory_store.list()
    if items:
        memory_list = "\n".join([f"  • {m}" for m in items])
        return f"Here are the things you asked me to remember:\n\n{memory_list}"
    return (
        "My memory is currently empty. Tell me to 'remember [something]' "
        "to save a note!"
    )
