# LoadStar Quality Framework

Canonical plan for test-driven code quality across the LoadStar codebase.
Imported by CLAUDE.md -- loaded every session.

## Architecture: Autonomous Convergence Loop

Based on the Ralph Loop pattern (state on disk, git as memory) and Anthropic's
long-running agent harness (initializer + coding agent, progress.txt, feature list).

```
┌─────────────────────────────────────────┐
│         $quality-check invoked          │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Read quality-status.json               │
│  (initialize if missing)                │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  All checks pass?  ──── YES ──► DONE   │
│  Max iterations?   ──── YES ──► STOP   │
└────────────────┬────────────────────────┘
                 │ NO
                 ▼
┌─────────────────────────────────────────┐
│  Pick highest-priority failing check    │
│  Run agent → fix → re-verify → update  │
│  Commit + log progress                 │
└────────────────┬────────────────────────┘
                 │
                 ▼
            LOOP BACK TO CONVERGENCE CHECK
```

**Key principles:**
1. State lives on disk (`quality-status.json`), not in model memory
2. One check per iteration (focused, verifiable progress)
3. Re-verification mandatory after every fix
4. Git commit after each iteration (cumulative memory)
5. Exploratory sweep runs last (discover unknowns after knowns are clean)
6. Max iterations safety valve (default: 10)

## Progress Tracker

`.cortex/quality-framework/quality-status.json` — JSON with per-check `passes: true/false`.
The coordinator reads this at the start of each iteration and updates it at the end.

`.cortex/quality-framework/progress.md` — Append-only log of each iteration's actions and lessons.

## Convergence Criteria

The loop is CONVERGED when ALL of:
- 0 critical findings across all checks
- 0 warning findings across all checks
- All live Snowflake object checks pass
- Exploratory sweep finds no undiscovered gaps

## Codebase Inventory

| Category | Files | Test Coverage |
|----------|-------|---------------|
| Python | `register_model.py`, `snowpark_session.py`, `streamlit/streamlit_app.py` | Via `python-linter` + `streamlit-tester` agents |
| SQL | 12 scripts (`00_setup_infrastructure.sql` through `10_create_git_integration.sql` + `99_teardown.sql`) | Via `sql-auditor` agent |
| Notebooks | `apex_nextload_demo.ipynb`, `notebooks/freight_360_demo.ipynb` | Via `notebook-auditor` agent |

## Agent Swarm

4 custom agents in `.cortex/agents/`, each with an embedded prompt contract:

| Agent | Tools | Scope |
|-------|-------|-------|
| `sql-auditor` | `["*"]` | SQL scripts + live Snowflake objects |
| `streamlit-tester` | `["Bash","Read","Grep","Glob"]` | Streamlit app static analysis |
| `notebook-auditor` | `["*"]` | Notebook cell-level validation |
| `python-linter` | `["Bash","Read","Grep"]` | Python scripts lint + security |

All agents use `memory: project` for cross-session learning.
All agents must output a `STATUS: PASS|FAIL critical=N warning=N info=N` line for machine parsing.

## Prompt Contract Shape (all agents)

```
Scope: MAY/MUST NOT boundaries
Output Schema: {summary table} + STATUS: PASS|FAIL critical=N warning=N info=N
Ask/Refuse: skip-and-note on errors, never halt
Validators: self-checks before returning
Tool-Proposal: propose fixes, never apply
```

## Coordinator Skill

`$quality-check` in `.cortex/skills/quality-check/SKILL.md`

Workflow: convergence loop — read status → check convergence → pick failing check → run agent → fix → re-verify → update status → commit → loop back

## Test Suite

`tests/` with `conftest.py` + 7 test files. Markers: `sql`, `streamlit`, `notebook`, `python`, `live`.

## Lessons Learned (Run 1 — 2026-02-20)

1. `ruff` not on PATH — use `python3 -m ruff` in all agent definitions
2. Background agents fail with "stream destroyed" — run as sequential foreground tasks
3. Streamlit HTML templates need E501 exemption (`ruff.toml` per-file-ignores)
4. Notebook cell IDs are in `id` field, not `metadata.name`
5. `snowflake_sql_execute` connection can terminate — agents should fall back to `snow sql -c se_demo` via Bash
6. BrokerRiskNet is 3-layer NN (input->32->16->1), not 2-layer as previously documented
7. SQL scripts use `FREIGHT_DEMO` naming but deployed env uses `APEX_CAPITAL_DEMO` — this is by design (template vs deployed)
8. `line-length = 120` in ruff.toml is the project standard

## Lessons Learned (Run 2 — 2026-02-20, Convergence Loop)

9. Exploratory sweep is essential — discovered LOADSTAR_RECOMMENDATIONS_V (undocumented view used by Streamlit) and missing requirements.txt
10. apex_nextload_demo.ipynb stakeholder references (Lance, Brendan, Michael) are by-design for the internal SE demo — notebook-auditor agent updated with exception rule
11. STAGING schema is empty (by design — reserved for future use)
12. Re-verification after fixes is critical — confirms fixes don't introduce new issues
13. Convergence loop completed in 11 iterations across 11 checks with 2 fixes applied
