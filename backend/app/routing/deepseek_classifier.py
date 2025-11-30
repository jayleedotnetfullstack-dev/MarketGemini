# backend/app/routing/deepseek_classifier.py
import re
from typing import Tuple
from enum import Enum

class DeepseekResolvedModel(str, Enum):
    # canonical, lowercase names (what tests use)
    chat = "deepseek-chat"
    v3 = "deepseek-v3"
    r1 = "deepseek-r1"

    # uppercase aliases (for your existing code, if any)
    CHAT = "deepseek-chat"
    V3 = "deepseek-v3"
    R1 = "deepseek-r1"


def classify_deepseek_model(prompt: str) -> Tuple[DeepseekResolvedModel, float, str]:
    text = (prompt or "").lower()

    score_chat = score_v3 = score_r1 = 0.0
    reasons = []

    r1_keywords = [
        "step by step", "step-by-step", "show your reasoning", "prove",
        "derive", "analyze deeply", "chain of reasoning",
        "math problem", "equation", "combinatorics", "probability",
        "why does this fail", "debug this algorithm",
    ]
    if any(k in text for k in r1_keywords):
        score_r1 += 2.0
        reasons.append("Reasoning keywords found → favor R1.")

    v3_keywords = [
        "api", "endpoint", "http", "rest", "graphql",
        "sql", "schema", "database", "index",
        "json", "yaml", "docker", "kubernetes", "k8s",
        "system design", "architecture", "microservice",
        "time complexity", "big o", "optimize the algorithm",
        "c#", "python", "java", "typescript", "javascript", "go", "rust",
        "leetcode", "binary tree", "graph", "dynamic programming",
    ]
    if any(k in text for k in v3_keywords):
        score_v3 += 2.0
        reasons.append("Technical / coding keywords → favor V3.")

    chat_keywords = [
        "explain like i'm five", "eli5", "in simple terms",
        "summarize", "tl;dr",
        "rewrite", "rephrase", "shorten", "make it shorter", "make it longer",
        "email", "subject line", "social media", "tweet", "post",
        "translate", "correct my grammar", "improve wording",
    ]
    if any(k in text for k in chat_keywords):
        score_chat += 2.0
        reasons.append("Summarization / simple explanation → favor Chat.")

    has_codey_chars = bool(re.search(r"[{}();=<>\[\]]", text))
    length = len(text)

    if length < 80 and not has_codey_chars:
        score_chat += 1.0
        reasons.append("Short, casual prompt → Chat.")
    elif length > 300 and has_codey_chars:
        score_v3 += 1.0
        reasons.append("Long + code-like → V3.")
    elif length > 300 and not has_codey_chars:
        score_r1 += 0.5
        score_v3 += 0.5
        reasons.append("Long text, ambiguous between V3 and R1.")

    scores = {
        DeepseekResolvedModel.CHAT: score_chat,
        DeepseekResolvedModel.V3: score_v3,
        DeepseekResolvedModel.R1: score_r1,
    }
    best_model = max(scores, key=scores.get)
    best_score = scores[best_model]

    max_possible = 3.0
    confidence = min(1.0, best_score / max_possible)

    if best_score <= 0.5:
        best_model = DeepseekResolvedModel.CHAT
        confidence = 0.2
        reasons.append("Prompt too broad / no strong signals → low confidence; default to Chat.")

    reason_text = " ".join(reasons) if reasons else "Heuristic routing applied."

    return best_model, confidence, reason_text

def confidence_label(score: float) -> str:
    if score >= 0.75:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    return "LOW"
