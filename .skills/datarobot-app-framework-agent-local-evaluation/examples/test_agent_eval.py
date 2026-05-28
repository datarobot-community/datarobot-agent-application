# Copy this file to agent/tests/test_agent_eval.py and replace the placeholder
# prompts and contexts with content relevant to your agent's domain.
#
# Prerequisites:
#   - Copy examples/moderation.yaml to agent/moderation.yaml and fill in
#     deployment IDs.
#   - Add to .env (or export before running):
#       TARGET_NAME=resultText
#   - Register the eval marker in pyproject.toml:
#       [tool.pytest.ini_options]
#       markers = ["eval: live evaluation tests requiring DataRobot credentials"]
#
# Run evaluation tests:
#   cd agent && uv run pytest tests/test_agent_eval.py -m eval -v
#
# Skip evaluation tests (no credentials needed):
#   cd agent && uv run pytest tests/ -m "not eval"

import pytest
from agent.myagent import custompy_adaptor
from datarobot_dome.api import ModerationPipeline

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def pipeline():
    """Load the ModerationPipeline once for the entire test session."""
    return ModerationPipeline.from_yaml("moderation.yaml")


# ── Basic goal accuracy ───────────────────────────────────────────────────────


@pytest.mark.eval
async def test_agent_goal_accuracy(pipeline):
    """Agent response should achieve the user's stated goal."""
    user_prompt = "What is the return policy?"
    completion_params = {
        "model": None,
        "messages": [{"role": "user", "content": user_prompt}],
        "stream": False,
    }
    response_obj = await custompy_adaptor(completion_params)

    result, _ = pipeline.evaluate_response(
        response_obj.response,  # extract text from CustomModelChatResponse
        prompt=user_prompt,
    )

    # result.blocked is True when any guard's threshold is breached
    assert not result.blocked, (
        f"Eval failed: {result.blocked_message} | Metrics: {result.metrics}"
    )


# ── Faithfulness (RAG hallucination detection) ────────────────────────────────


@pytest.mark.eval
async def test_agent_faithfulness(pipeline):
    """Agent response should not hallucinate facts outside the retrieved context."""
    user_prompt = "What is the return policy?"
    retrieved_context = ["Returns are accepted within 30 days of purchase."]

    completion_params = {
        "model": None,
        "messages": [{"role": "user", "content": user_prompt}],
        "stream": False,
    }
    response_obj = await custompy_adaptor(completion_params)

    result, _ = pipeline.evaluate_response(
        response_obj.response,
        prompt=user_prompt,
        retrieved_contexts=retrieved_context,  # required for faithfulness
    )

    assert not result.blocked, f"Hallucination detected: {result.blocked_message}"


# ── Parametrized evaluation dataset ──────────────────────────────────────────


TEST_CASES = [
    # Replace with prompt/context pairs relevant to your agent's domain.
    {
        "prompt": "What is the return policy?",
        "context": ["Returns are accepted within 30 days of purchase."],
    },
    {
        "prompt": "How do I reset my password?",
        "context": ["Click 'Forgot password' on the login page."],
    },
]


@pytest.mark.eval
@pytest.mark.parametrize("case", TEST_CASES)
async def test_faithfulness_parametrized(pipeline, case):
    """All test cases should pass faithfulness evaluation."""
    completion_params = {
        "model": None,
        "messages": [{"role": "user", "content": case["prompt"]}],
        "stream": False,
    }
    response_obj = await custompy_adaptor(completion_params)

    result, _ = pipeline.evaluate_response(
        response_obj.response,
        prompt=case["prompt"],
        retrieved_contexts=case["context"],
    )
    assert not result.blocked, (
        f"Failed on prompt '{case['prompt']}': {result.blocked_message}"
    )


# ── Negative test ─────────────────────────────────────────────────────────────


@pytest.mark.eval
def test_pipeline_catches_hallucination(pipeline):
    """The evaluation pipeline must correctly identify a hallucinated response."""
    result, _ = pipeline.evaluate_response(
        "Returns are not accepted under any circumstances.",  # deliberately wrong
        prompt="What is the return policy?",
        retrieved_contexts=["Returns are accepted within 30 days of purchase."],
    )
    assert result.blocked, "The evaluation pipeline should have caught the hallucination."
