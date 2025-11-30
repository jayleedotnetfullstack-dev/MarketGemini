import pytest

from app.routing.deepseek_classifier import (
    classify_deepseek_model,
    DeepseekResolvedModel,
    confidence_label,
)


@pytest.mark.parametrize(
    "prompt, expected_model",
    [
        ("Explain soccer to a 7-year-old", DeepseekResolvedModel.chat),
        ("Help me write a polite email to my manager", DeepseekResolvedModel.chat),
        ("What is React and how does it compare to Angular?", DeepseekResolvedModel.chat),
    ],
)
def test_classifier_prefers_chat_for_simple_prompts(prompt, expected_model):
    model, score, reason = classify_deepseek_model(prompt)
    assert model == expected_model
    assert 0.0 <= score <= 1.0
    assert isinstance(reason, str)


@pytest.mark.parametrize(
    "prompt",
    [
        "Given this SQL schema and performance metrics, suggest an index strategy.",
        "Refactor this Python function to be O(n log n) and explain why.",
    ],
)
def test_classifier_prefers_v3_for_technical_prompts(prompt):
    model, score, _ = classify_deepseek_model(prompt)
    assert model in (DeepseekResolvedModel.v3, DeepseekResolvedModel.chat)
    assert score >= 0.4


@pytest.mark.parametrize(
    "prompt",
    [
        "Step by step, reason about whether gold or T-bills will perform better under 5% inflation.",
        "Let's do chain-of-thought: prove that the sum of two even numbers is even.",
    ],
)
def test_classifier_can_pick_r1_for_reasoning(prompt):
    model, score, _ = classify_deepseek_model(prompt)
    assert model in (DeepseekResolvedModel.r1, DeepseekResolvedModel.v3)
    assert score >= 0.4


@pytest.mark.parametrize(
    "score, expected_label",
    [
        (0.9, "HIGH"),
        (0.7, "MEDIUM"),
        (0.3, "LOW"),
    ],
)
def test_confidence_label(score, expected_label):
    assert confidence_label(score) == expected_label
