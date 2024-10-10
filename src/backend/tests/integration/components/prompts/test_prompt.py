from langflow.components.prompts import PromptComponent
from langflow.schema.message import Message
from tests.integration.utils import run_single_component

import pytest


@pytest.mark.asyncio
async def test():
    outputs = await run_single_component(PromptComponent, inputs={"template": "test {var1}", "var1": "from the var"})
    print(outputs)
    assert isinstance(outputs["prompt"], Message)
    assert outputs["prompt"].text == "test from the var"
