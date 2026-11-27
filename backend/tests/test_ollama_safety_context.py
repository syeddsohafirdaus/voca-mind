import json
from unittest.mock import MagicMock, patch

import pytest

from app.ai.ollama_generator import OllamaResponseGenerator


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state, expected",
    [
        ("LOW", False),
        ("CONCERN", True),
    ],
)
async def test_ollama_safety_context(state, expected):

    generator = OllamaResponseGenerator()

    response = MagicMock()
    response.read.return_value = json.dumps({
        "message": {
            "content": "I am here to listen."
        }
    }).encode("utf-8")

    response.__enter__.return_value = response

    with patch(
        "app.ai.ollama_generator.urllib.request.urlopen",
        return_value=response,
    ) as mocked:

        await generator.generate_response(
            message="I had a difficult day.",
            context={
                "safety_state": state,
                "conversation_history": [],
            },
        )

        request = mocked.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))

        system_prompt = payload["messages"][0]["content"]

        assert (
            "CURRENT SAFETY ROUTING: CONCERN"
            in system_prompt
        ) == expected

        assert payload["messages"][0]["role"] == "system"

        assert payload["messages"][-1]["content"] == (
            "I had a difficult day."
        )
