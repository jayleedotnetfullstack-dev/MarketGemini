def extract_prompt(messages):
    if not messages:
        return ""
    last = messages[-1]
    if isinstance(last, dict):
        return last.get("content", "")
    if hasattr(last, "content"):
        return last.content
    return str(last)
