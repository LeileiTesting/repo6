# Specification: cost-center-agent

> **Guidelines**: Read all applicable guidelines before executing ANY tasks below:
> - [guidelines.md](../guidelines.md) — Universal execution rules
> - [guidelines-agent.md](../guidelines-agent.md) — Universal agent patterns
> - [guidelines-agent-python.md](../guidelines-agent-python.md) — Python implementation details
> - [guidelines-agent-skills.md](../guidelines-agent-skills.md) — Runtime skills patterns
> - [guidelines-agent-mcp.md](../guidelines-agent-mcp.md) — MCP integration patterns

---

## Basic Setup

- [x] Read `intent.md` for project context (Finance Controllers NL querying of cost center data via CE_COSTCENTER_0001 MCP)
- [x] Bootstrap agent code in `assets/cost-center-agent/` using instructions from the `sap-agent-bootstrap` section (invoke from inside `assets/cost-center-agent/`, use copy commands — do NOT create files manually)
- [x] Install dependencies, validate the agent starts and responds at `/.well-known/agent.json`

---

## Runtime Skills

No runtime skills needed — query logic is simple enough for the system prompt (single data domain, no complex branching or reference material required).

---

## Project-Specific Tasks

### Agent Identity & System Prompt

- [x] Set agent name: `Cost Center Intelligence Agent`
- [x] Set agent description: `AI agent for Finance Controllers to query SAP S/4HANA cost center data using natural language. Answers questions about total count of cost centers and top 5 cost centers instantly.`
- [x] Write the `@prompt_section` system prompt in `app/agent.py` with these instructions:
  - You are a Finance Controller assistant. You answer questions about SAP S/4HANA cost center data.
  - You MUST use tools to retrieve live data. NEVER fabricate, guess, or invent cost center information.
  - For questions about **total count** of cost centers: call `listCostCenters` with `count=true` and `top=1` to retrieve `@odata.count`.
  - For questions about **top 5 cost centers**: call `listCostCenters` with `top=5` and `orderby=CostCenter asc`, selecting `CostCenter, CostCenterName, CostCenterDescription, ControllingArea, CompanyCode`.
  - Always set page size (`top`) to a maximum of 100 on tool calls that accept it.
  - Present results in a clear, structured format: numbered list for top 5, plain number for count.
  - If a tool returns an error, relay the error message exactly as received.
  - You only answer questions about cost centers. For any other topic, politely redirect the user.

### MCP Tool Integration (Path B — Existing MCP Server)

- [x] MCP spec file already exists at `specification/cost-center-agent/mcp-specs/mcp-spec-CE_COSTCENTER_0001-listCostCenters.json`
- [x] Wire MCP tool loading in `app/agent.py` using `get_mcp_tools()` from `mcp_tools` module (bootstrap-generated indirection layer). NEVER import directly from `sap_cloud_sdk.agentgateway`. NEVER create direct HTTP clients.
- [x] Add MCP server dependency to `asset.yaml` under `requires`:
  ```yaml
  requires:
    - name: ce-costcenter-0001-mcp
      kind: mcp-server
      ordId: sap.s4:apiResource:CE_COSTCENTER_0001:v1
  ```
- [x] Generate `mcp-mock.json` using the `mcp-mock-config` skill, based on `specification/cost-center-agent/mcp-specs/mcp-spec-CE_COSTCENTER_0001-listCostCenters.json`. The mock must include:
  - `listCostCenters` with count=true response: `{ "@odata.count": 42, "value": [{"CostCenter": "1000", "CostCenterName": "Administration"}] }`
  - `listCostCenters` with top=5 response: array of 5 cost center objects with CostCenter, CostCenterName, CostCenterDescription, ControllingArea, CompanyCode fields

### Cost Center Query Logic

- [x] Implement natural language understanding in the system prompt to map:
  - "How many cost centers?" / "total count" / "count of cost centers" → `listCostCenters(count=true, top=1)`
  - "Top 5 cost centers" / "first 5 cost centers" / "list cost centers" → `listCostCenters(top=5, orderby="CostCenter asc", select="CostCenter,CostCenterName,CostCenterDescription,ControllingArea,CompanyCode")`
  - Filtered queries (e.g. "cost centers in controlling area 1000") → `listCostCenters(filter="ControllingArea eq '1000'", top=100)`
- [x] Verify agent correctly extracts `@odata.count` from tool response for count queries
- [x] Verify agent formats top-5 results as a numbered list with Name and ID

---

## Business Instrumentation

- [x] Implement business step instrumentation for each milestone from `intent.md`:
  - `M1`: User query received — log `[M1.achieved]: Query received from Finance Controller: {query_summary}`
  - `M2`: Intent resolved — log `[M2.achieved]: Intent resolved to {query_type}` or `[M2.missed]: Could not resolve intent`
  - `M3`: S/4HANA data fetched — log `[M3.achieved]: Cost center data fetched successfully` or `[M3.missed]: Tool call failed: {error}`
  - `M4`: Answer formulated — log `[M4.achieved]: Answer formulated with {result_count} cost centers`
  - `M5`: Response delivered — log `[M5.achieved]: Response delivered to controller`
- [x] Use OpenTelemetry spans for each milestone (decorator form on regular async methods, context manager inside non-generator async functions)
- [x] NEVER use `with tracer.start_as_current_span(...)` inside an async generator (`stream()`). Extract all business logic into `_run_agent()` helper and instrument that instead.
- [x] Verify `auto_instrument()` is called at top of `main.py` before any AI framework imports

---

## MCP Mock Configuration

- [x] Invoke `mcp-mock-config` skill to generate `assets/cost-center-agent/mcp-mock.json`
- [x] Mock responses must cover:
  - **Count query**: `{ "@odata.count": 42, "value": [{"CostCenter": "0000001000", "CostCenterName": "Administration", "ControllingArea": "A000"}] }`
  - **Top 5 query**: Array of 5 objects: `[{"CostCenter": "0000001000", "CostCenterName": "Administration", "CostCenterDescription": "Corporate Administration", "ControllingArea": "A000", "CompanyCode": "1010"}, {"CostCenter": "0000001100", "CostCenterName": "Finance", "CostCenterDescription": "Finance Department", "ControllingArea": "A000", "CompanyCode": "1010"}, {"CostCenter": "0000001200", "CostCenterName": "HR", "CostCenterDescription": "Human Resources", "ControllingArea": "A000", "CompanyCode": "1010"}, {"CostCenter": "0000001300", "CostCenterName": "IT", "CostCenterDescription": "Information Technology", "ControllingArea": "A000", "CompanyCode": "1010"}, {"CostCenter": "0000001400", "CostCenterName": "Marketing", "CostCenterDescription": "Marketing Department", "ControllingArea": "A000", "CompanyCode": "1010"}]`

---

## Testing

- [x] `conftest.py` only sets `IBD_TESTING=true` — mock MCP tool results come from `mcp-mock.json` via bootstrap fixture
- [x] Write unit test `tests/test_list_cost_centers.py` — test `listCostCenters` tool is called correctly for count and top-5 queries; run immediately after writing
- [x] Write integration test `tests/test_agent_integration.py` — end-to-end: call agent `invoke()` with (a) "How many cost centers are there?" and verify count answer, (b) "Show me the top 5 cost centers" and verify list answer. Mock LLM (ChatLiteLLM) to return canned responses. Tests must run offline.
- [x] Run `pytest` from `assets/cost-center-agent/` (no args) — 49 tests passed, 71% coverage
- [x] Verify `assets/cost-center-agent/app/agent.py` has exactly 5 decorated functions: confirmed 5
- [x] Run `pytest` again (no args) to generate final `test_report.json`
- [x] Verify `test_report.json` exists in `assets/cost-center-agent/`
