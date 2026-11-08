"""A deliberately non-conformant solution, kept as a fixture for the conformance check. It shows the shortcuts a
first prototype often takes; `eca conformance` must flag every one of them. Never deploy this."""

import openai  # noqa: F401  # violates AS-03: a model SDK called directly, bypassing the platform client

SPEC = {
    "name": "prototype-assistant",
    "servers": ["plm", "changes"],
    "untrusted_inputs": ["request.attachment"],
    "decision": "model",
    "policy": "decide",
    "reviewer": False,
    "eval_suite": "data/prototype_cases.jsonl",
    "approval_roles": None,
}
MODEL = "gpt-4o"  # violates AS-09: a model name hard-coded


def decide(model, text):
    return model.complete(f"Should this change be approved? {text}")  # violates AS-02


async def release(client, request_id):
    # violates AS-07: releases a change order without collecting signatures
    return await client.call_tool("release_change_order", {"request_id": request_id, "crash_relevant": True,
                                                           "signatures": []})
