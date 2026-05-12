# Architecture deep-dive

This document walks the data flow for a single user query end-to-end so
the design choices are obvious to a reviewer.

## End-to-end flow for: *"What tools does APT41 use?"*

### 1. Frontend (Next.js)
- User types into `ChatInput`. The selected tool list (from
  `ToolSelector`) is the user's "human-in-the-loop knob"; they can
  disable, e.g., web search if they want a closed-source answer.
- `streamChat()` posts to `/chat` and parses Server-Sent Events.

### 2. FastAPI (`api/main.py`)
- Generates a `run_id`, logs the run in Postgres `agent_runs`.
- Builds the LangGraph state and streams `graph.astream(stream_mode="updates")`.
- Each node update is mapped to an SSE `agent_step` event.
- On completion, emits `final` with the answer + duration_ms.

### 3. Orchestrator agent (`agents/orchestrator.py`)
- Loads `prompts/orchestrator.txt` (one-shot example baked in).
- Calls Qwen via `LLM_BASE_URL`. Expects strict JSON.
- Output:
  ```json
  {"intent":"threat_actor_profile",
   "writer_template":"threat_actor_profile",
   "tools_to_use":["graph_query","vector_search","keyword_search"],
   "entities":{"threat_actors":["APT41"], ...},
   "rationale":"Threat-actor question with malware overlap"}
  ```
- The plan is intersected with the user's selected tool set (so the
  user always wins).

### 4. Retrieval agent (`agents/retrieval.py`)
- Loads MCP tools via `langchain-mcp-adapters` (one connection per MCP
  server, `transport="sse"`).
- Filters tools to the orchestrator's `tools_to_use`.
- Hands them to `langgraph.prebuilt.create_react_agent` along with our
  ReACT prompt (`prompts/retrieval_react.txt`).
- Each tool call + response is captured into our trace structure for
  the UI:
  ```json
  {"agent":"retrieval","phase":"action","content":{"tool":"graph_query","args":{"entity_name":"APT41","query_type":"uses"}}}
  ```

### 5. MCP servers
Three FastMCP processes serving SSE on ports 8101 / 8102 / 8103.
Each one uses a `ToolRegistry` so tools are functions, and adding one is
one decorator.

```python
@registry.register()
def graph_query(entity_name, query_type="uses", limit=50):
    """Cypher query helpers..."""
    return GraphClient(...).actor_uses(entity_name, limit=limit)
```

### 6. Writer agent (`agents/writer.py`)
- Picks a template based on `plan.writer_template` (one of 5).
- Each template has a baked-in one-shot example.
- If the previous validator round gave feedback, that feedback is
  appended to the prompt for the retry round.

### 7. Validator agent (`agents/validator.py`)
- Strict JSON: `{valid, issues, feedback}`.
- LangGraph conditional edge: if `valid=false` and
  `retry_count < MAX_VALIDATION_RETRIES`, the graph routes back to
  `writer` with the validator's feedback in state.

### 8. Feedback persistence
- The completed `run_id` is in the SSE `final` event.
- User clicks 👍/👎 → `POST /feedback` writes to `feedback` table.
- Future training: `SELECT user_query, final_answer FROM agent_runs JOIN feedback ON ... WHERE rating=1` is your DPO/RLHF positive set.

---

## State object

`agents/state.CTIState` is the single source of truth that every node
reads + writes:

| Key | Producer | Consumer |
|---|---|---|
| `user_query` | API | all nodes |
| `selected_tools` | API | orchestrator |
| `available_tools` | API | orchestrator |
| `plan` | orchestrator | retrieval, writer |
| `evidence` | retrieval | writer, validator |
| `answer` | writer | validator, API |
| `validation` | validator | writer (retry), API |
| `retry_count` | validator | graph router |
| `trace` | every node | API → UI |

---

## Where to extend

| Want to add… | Touch this file |
|---|---|
| A new retrieval source | `mcp_servers/retrieval_mcp/server.py` (one function) |
| A new enrichment provider | `mcp_servers/enrichment_mcp/adapters.py` (one class) |
| A new writer template (e.g. STIX bundle export) | `agents/prompts/writer_<name>.txt` + add to `_TEMPLATE_MAP` in `writer.py` + add intent in `orchestrator.txt` |
| A new chat front-end | Replace `frontend/`, keep the SSE contract |
| Trace storage / replay | Add a route over `agent_runs` table |
