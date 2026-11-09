"""Unit tests for the listCostCenters MCP tool mock behavior."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure app/ is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

# Set IBD_TESTING so mcp_providers.agw uses mock tools
os.environ["IBD_TESTING"] = "1"


def _load_mock_data():
    mock_file = Path(__file__).parent.parent / "mcp-mock.json"
    return json.loads(mock_file.read_text())


class TestListCostCentersMockTool:
    """Tests that the listCostCenters mock tool returns expected data."""

    def test_mock_file_exists(self):
        mock_file = Path(__file__).parent.parent / "mcp-mock.json"
        assert mock_file.exists(), "mcp-mock.json must exist"

    def test_mock_has_ce_costcenter_server(self):
        data = _load_mock_data()
        assert "CE_COSTCENTER_0001" in data["servers"], (
            "CE_COSTCENTER_0001 server must be present in mock data"
        )

    def test_mock_has_list_cost_centers_tool(self):
        data = _load_mock_data()
        tools = data["servers"]["CE_COSTCENTER_0001"]["tools"]
        assert "listCostCenters" in tools, "listCostCenters tool must be present"

    def test_mock_response_has_count(self):
        data = _load_mock_data()
        mock_response = data["servers"]["CE_COSTCENTER_0001"]["tools"]["listCostCenters"]["mock_response"]
        assert "@odata.count" in mock_response, "Mock response must contain @odata.count"
        assert isinstance(mock_response["@odata.count"], int), "@odata.count must be an integer"
        assert mock_response["@odata.count"] > 0, "@odata.count must be positive"

    def test_mock_response_has_value_array(self):
        data = _load_mock_data()
        mock_response = data["servers"]["CE_COSTCENTER_0001"]["tools"]["listCostCenters"]["mock_response"]
        assert "value" in mock_response, "Mock response must contain 'value' array"
        assert isinstance(mock_response["value"], list), "'value' must be a list"
        assert len(mock_response["value"]) >= 5, "Mock response must contain at least 5 cost centers for top-5 queries"

    def test_mock_response_cost_center_fields(self):
        data = _load_mock_data()
        items = data["servers"]["CE_COSTCENTER_0001"]["tools"]["listCostCenters"]["mock_response"]["value"]
        required_fields = ["CostCenter", "CostCenterName", "ControllingArea", "CompanyCode"]
        for item in items[:5]:
            for field in required_fields:
                assert field in item, f"Cost center item must have '{field}' field"

    def test_mock_top_5_returns_five_items(self):
        data = _load_mock_data()
        items = data["servers"]["CE_COSTCENTER_0001"]["tools"]["listCostCenters"]["mock_response"]["value"]
        # Simulate top=5 by slicing
        top_5 = items[:5]
        assert len(top_5) == 5, "Must be able to retrieve 5 cost centers"

    def test_mock_count_query(self):
        """Verify count field is available for total count queries."""
        data = _load_mock_data()
        count = data["servers"]["CE_COSTCENTER_0001"]["tools"]["listCostCenters"]["mock_response"]["@odata.count"]
        assert count == 42, "Mock count should be 42 as defined in mcp-mock.json"

    @pytest.mark.asyncio
    async def test_mock_tools_loaded_in_testing_mode(self):
        """Verify that IBD_TESTING=1 causes mock tools to be loaded."""
        from mcp_providers.agw import get_mcp_tools
        tools = await get_mcp_tools()
        assert len(tools) > 0, "Mock tools should be loaded when IBD_TESTING=1"
        tool_names = [t.name for t in tools]
        assert "listCostCenters" in tool_names, "listCostCenters must be available as a mock tool"

    @pytest.mark.asyncio
    async def test_mock_tool_returns_cost_center_data(self):
        """Verify the mock tool returns the expected cost center data."""
        from mcp_providers.agw import get_mcp_tools
        tools = await get_mcp_tools()
        list_tool = next(t for t in tools if t.name == "listCostCenters")
        result = await list_tool.arun({})
        response = json.loads(result)
        assert "@odata.count" in response, "Tool response must contain @odata.count"
        assert "value" in response, "Tool response must contain 'value'"
