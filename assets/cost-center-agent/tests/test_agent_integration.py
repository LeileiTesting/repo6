"""Integration tests for the Cost Center Intelligence Agent."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure app/ is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

# Set IBD_TESTING before any agent imports
os.environ["IBD_TESTING"] = "1"


def _make_llm_message(content: str):
    """Create a mock LLM message."""
    msg = MagicMock()
    msg.content = content
    return msg


def _make_graph_result(response_text: str):
    """Create a mock LangGraph result with the given response text."""
    return {"messages": [_make_llm_message(response_text)]}


class TestCostCenterAgentIntegration:
    """End-to-end integration tests for the Cost Center Intelligence Agent."""

    @pytest.mark.asyncio
    async def test_count_query_returns_answer(self):
        """Agent correctly answers 'How many cost centers are there?' using mock data."""
        from agent import SampleAgent

        agent = SampleAgent()
        expected_response = "There are **42** cost centers in total in SAP S/4HANA Controlling."

        # Mock the LLM graph invocation to return the expected response
        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = _make_graph_result(expected_response)

            response = await agent.invoke(
                query="How many cost centers are there?",
                context_id="test-session-count",
            )

        assert response.status == "completed"
        assert response.message == expected_response
        mock_invoke.assert_called_once()

        # Verify correct query was passed
        call_kwargs = mock_invoke.call_args
        assert "How many cost centers" in call_kwargs.kwargs.get("query", call_kwargs.args[2] if len(call_kwargs.args) > 2 else "")

    @pytest.mark.asyncio
    async def test_top_5_query_returns_list(self):
        """Agent correctly answers 'Show me the top 5 cost centers' using mock data."""
        from agent import SampleAgent

        agent = SampleAgent()
        expected_response = (
            "Here are the top 5 cost centers:\n\n"
            "1. **0000001000** - Administration (Corporate Administration) | Controlling Area: A000 | Company Code: 1010\n"
            "2. **0000001100** - Finance (Finance Department) | Controlling Area: A000 | Company Code: 1010\n"
            "3. **0000001200** - HR (Human Resources) | Controlling Area: A000 | Company Code: 1010\n"
            "4. **0000001300** - IT (Information Technology) | Controlling Area: A000 | Company Code: 1010\n"
            "5. **0000001400** - Marketing (Marketing Department) | Controlling Area: A000 | Company Code: 1010"
        )

        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = _make_graph_result(expected_response)

            response = await agent.invoke(
                query="Show me the top 5 cost centers",
                context_id="test-session-top5",
            )

        assert response.status == "completed"
        assert response.message == expected_response
        mock_invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_uses_mock_tools_in_testing_mode(self):
        """In IBD_TESTING mode, agent loads mock MCP tools from mcp-mock.json."""
        from mcp_providers.agw import get_mcp_tools

        tools = await get_mcp_tools()
        assert len(tools) > 0, "Agent must load mock tools in IBD_TESTING mode"

        tool_names = [t.name for t in tools]
        assert "listCostCenters" in tool_names, "listCostCenters tool must be available"

    @pytest.mark.asyncio
    async def test_agent_stream_returns_completed_status(self):
        """Agent stream() yields a completed status on success."""
        from agent import SampleAgent

        agent = SampleAgent()
        test_response = "The total number of cost centers is 42."

        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = _make_graph_result(test_response)

            results = []
            async for chunk in agent.stream(
                query="How many cost centers are there?",
                context_id="test-session-stream",
            ):
                results.append(chunk)

        assert len(results) >= 2, "Stream must yield at least 2 chunks (processing + response)"
        # First chunk is the processing indicator
        assert results[0]["is_task_complete"] is False
        # Last chunk is the completed response
        final = results[-1]
        assert final["is_task_complete"] is True
        assert final["require_user_input"] is False
        assert final["content"] == test_response

    @pytest.mark.asyncio
    async def test_agent_stream_handles_errors_gracefully(self):
        """Agent stream() returns error status when an exception occurs."""
        from agent import SampleAgent

        agent = SampleAgent()

        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.side_effect = Exception("LLM connection failed")

            results = []
            async for chunk in agent.stream(
                query="How many cost centers are there?",
                context_id="test-session-error",
            ):
                results.append(chunk)

        final = results[-1]
        assert final["is_task_complete"] is True
        assert "error" in final["content"].lower() or "encountered" in final["content"].lower()

    @pytest.mark.asyncio
    async def test_agent_instrumentation_logs_milestones(self, caplog):
        """Agent logs business milestones when processing a query."""
        import logging
        from agent import SampleAgent

        agent = SampleAgent()
        test_response = "There are 42 cost centers."

        with patch.object(agent, "_invoke_with_fallback", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = _make_graph_result(test_response)

            with caplog.at_level(logging.INFO, logger="agent"):
                response = await agent.invoke(
                    query="How many cost centers?",
                    context_id="test-milestone-session",
                )

        # Check that milestone logs were emitted
        log_text = " ".join(caplog.messages)
        assert "M1.achieved" in log_text or "M2.achieved" in log_text or "M3.achieved" in log_text, (
            "Agent must emit at least one milestone log"
        )
        assert response.status == "completed"
