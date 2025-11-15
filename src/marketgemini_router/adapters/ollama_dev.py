import time, math
def _tok(s: str): return max(1, math.ceil(len(s)/4))

def chat(cfg, messages, profile):
    # TODO: replace with real Ollama /api/chat call in DEV
    t0 = time.time()
    content = f"[ollama mock] profile={profile}; echo: {messages[-1]['content'] if messages else ''}"
    dur = int((time.time()-t0)*1000)
    ti = _tok(" ".join(m["content"] for m in messages))
    to = _tok(content)
    return content, ti, to, dur
