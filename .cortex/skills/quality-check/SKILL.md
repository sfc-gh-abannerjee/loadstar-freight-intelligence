---
name: quality-check
description: "Run autonomous convergence loop: agents audit, fix, re-verify until all checks pass or max iterations. Use when: code quality, run tests, verify code, pre-flight check, quality check. Triggers: quality check, run quality, check code, pre-flight."
---

# Quality Check Coordinator — Autonomous Convergence Loop

Orchestrates 4 specialized agents in a convergence loop (Ralph Loop pattern).
State lives on disk in `quality-status.json`. Each iteration picks the highest-priority
failing check, runs the relevant agent, applies fixes, re-verifies, and updates status.
The loop continues until ALL checks pass or max iterations is reached.

## Key Files

- **Status tracker:** `.cortex/quality-framework/quality-status.json`
- **Progress log:** `.cortex/quality-framework/progress.md`
- **Agent definitions:** `.cortex/agents/{sql-auditor,streamlit-tester,notebook-auditor,python-linter}.md`
- **Lessons & plan:** `.cortex/quality-framework/PLAN.md`

## Prerequisites

1. `python3 -m ruff --version` succeeds
2. Snowflake connection `se_demo` active (test with `SELECT CURRENT_ACCOUNT()`)
3. Agent definitions exist in `.cortex/agents/`

**If any prerequisite fails:** STOP and report how to fix it.

## Convergence Loop

Execute the following loop. Do NOT stop after a single pass.

### Step 1: Read Status

Read `.cortex/quality-framework/quality-status.json`.
If it does not exist, create it using the template from PLAN.md (all checks `passes: false`).
Note the current `iteration` count.

### Step 2: Check Convergence

Evaluate all entries in `checks`:
- **CONVERGED** if every check has `passes: true`
  - Output: "QUALITY LOOP COMPLETE — all N checks pass after M iterations."
  - Append final summary to `progress.md`
  - Present final report to user
  - **STOP**

- **MAX ITERATIONS** if `iteration >= max_iterations`
  - Output: "MAX ITERATIONS REACHED (N). Remaining failures: [list]"
  - Append summary to `progress.md`
  - Present report of what passed and what still fails
  - **STOP**

- Otherwise: **CONTINUE** to Step 3.

### Step 3: Pick Highest-Priority Failing Check

From all checks where `passes: false`, pick the one with the highest priority:

**Priority order** (highest first):
1. Any check with `critical > 0` (fix critical issues first)
2. `credential_scan` (security always trumps style)
3. `sql_live_objects` (live Snowflake validation)
4. `sql_data_integrity`
5. `sql_udf_edge_cases`
6. `sql_task_health`
7. `sql_scripts`
8. `notebook_code_valid`
9. `notebook_structure`
10. `python_lint`
11. `streamlit_lint`
12. `doc_accuracy` (verify documentation claims match reality)
13. `script_correctness` (verify deploy/validate scripts reference correct names and paths)
14. `spec_traceability` (every SPEC.md deliverable verified against live objects + code)
15. `test_execution` (actually run pytest and confirm tests pass)
16. `streamlit_live` (verify Streamlit app deployed in Snowflake)
17. `exploratory_sweep` (always last — run only after all predefined checks pass)

If the selected check's `agent` field is `"all"` (exploratory_sweep), run all 4 agents
with expanded scope prompts (see Exploratory Sweep section below).

### Step 4: Run Agent

Launch the relevant agent as a **foreground** `general-purpose` Task (subagent_type: general-purpose, agent_mode: autonomous).

**Agent prompt template:**
```
You are the {agent_name} agent. Read .cortex/agents/{agent_name}.md and follow it exactly.

Focus on the following check category: {check_name}
Check description: {check_description}

IMPORTANT: At the very end of your report, output a machine-parseable status line:
STATUS: PASS|FAIL critical=N warning=N info=N

Where N is the count of findings at each severity level.
If there are 0 critical and 0 warning findings, output STATUS: PASS critical=0 warning=0 info=N
Otherwise output STATUS: FAIL critical=N warning=N info=N
```

**Scope mapping** (which agent for which check):
| Check | Agent | Specific Focus |
|-------|-------|----------------|
| python_lint | python-linter | Ruff lint + architecture + error handling + imports on register_model.py, snowpark_session.py |
| streamlit_lint | streamlit-tester | Full audit of streamlit/streamlit_app.py |
| sql_scripts | sql-auditor | Syntax validation + idempotency on SQL scripts only (no live queries) |
| sql_live_objects | sql-auditor | Object existence checks only (SHOW commands) |
| sql_data_integrity | sql-auditor | Row counts, column checks, dynamic table refresh |
| sql_udf_edge_cases | sql-auditor | UDF edge case queries only |
| sql_task_health | sql-auditor | Task health check only |
| notebook_structure | notebook-auditor | Cell structure, duplicate IDs, markdown quality |
| notebook_code_valid | notebook-auditor | SQL EXPLAIN + Python syntax on notebook cells |
| credential_scan | python-linter | Credential scan across ALL files (*.py, *.ipynb, *.sql, *.yml) |
| doc_accuracy | general-purpose | Read CLAUDE.md, README.md, DEPLOYMENT_GUIDE.md. Cross-reference every claim against actual files (glob) and live objects (snowflake_sql_execute). Flag any mismatch as WARNING. |
| script_correctness | general-purpose | Read deploy.sh, validate_deployment.sh, upload_notebook.sh. Verify every referenced table/object name matches CLAUDE.md deployed objects. Verify every file path reference resolves. Flag wrong names/paths as CRITICAL. |
| spec_traceability | general-purpose | Read SPEC.md and GAP_TRACKER.md. For every checked item in GAP_TRACKER.md, verify the artifact still exists (live query or file read). For every unchecked item, confirm it is genuinely unautomatable. Flag false claims as CRITICAL. |
| test_execution | general-purpose | Run `python3 -m pytest tests/ -v --tb=short` from project root. Parse results. Any test failure = WARNING. pytest not runnable = INFO (skip). |
| streamlit_live | sql-auditor | Run SHOW STREAMLITS IN SCHEMA APEX_CAPITAL_DEMO.ANALYTICS to verify LOADSTAR_COMMANDER exists and is active. |

### Step 5: Parse Results

From the agent's output, extract:
1. The `STATUS:` line (PASS or FAIL with counts)
2. The list of specific findings (if any)

If the agent did not output a `STATUS:` line, parse the summary table manually.

### Step 6: Apply Fixes (if FAIL)

If the status is FAIL:
1. For each finding at CRITICAL or WARNING severity:
   - Read the agent's proposed fix
   - Apply the fix using Edit/Write tools
   - Log what was changed
2. Skip INFO-level findings (document them but don't fix)

If the status is PASS:
- Skip to Step 8

### Step 7: Re-Verify

After applying fixes, re-run the SAME agent with the SAME prompt to verify:
- The fix actually resolved the finding
- No new issues were introduced

Parse the re-verification `STATUS:` line.

### Step 8: Update Status

Update `quality-status.json`:
1. Set the check's `passes` to `true` (if PASS) or `false` (if still FAIL)
2. Update `findings`, `critical`, `warnings` counts
3. Set `last_run` to current ISO timestamp
4. Increment `iteration` by 1
5. Append an entry to the `history` array:
   ```json
   {
     "iteration": N,
     "check": "check_name",
     "status": "PASS|FAIL",
     "findings_before": N,
     "findings_after": N,
     "fixes_applied": ["description of each fix"],
     "timestamp": "ISO timestamp"
   }
   ```

### Step 9: Log Progress

Append to `.cortex/quality-framework/progress.md`:
```markdown
## Iteration N — YYYY-MM-DD HH:MM
- **Check:** check_name
- **Status before:** FAIL (critical=N, warning=N)
- **Actions taken:** [list of fixes]
- **Status after:** PASS|FAIL (critical=N, warning=N)
- **Files changed:** [list]
- **Lessons:** [any new patterns discovered]
---
```

### Step 10: Encode Lessons

If new patterns or gotchas were discovered during this iteration:
1. Update the relevant agent definition in `.cortex/agents/` with the new lesson
2. Append to the "Lessons Learned" section in `.cortex/quality-framework/PLAN.md`

### Step 11: Loop Back

**GO TO Step 2.** Do not stop. Do not ask the user. Continue the loop.

The only valid stopping points are:
- Step 2: ALL checks pass (convergence)
- Step 2: Max iterations reached
- Prerequisites fail (Step 0)

## Exploratory Sweep

When the `exploratory_sweep` check is selected (all predefined checks already pass):

Run a discovery sweep that goes BEYOND the predefined inventory:

1. **File discovery:** `glob **/*.py **/*.sql **/*.ipynb **/*.yml` — find any files NOT in the predefined agent target lists
2. **Snowflake object discovery:** Run `SHOW TABLES/VIEWS/DYNAMIC TABLES/STREAMS/TASKS/PROCEDURES/FUNCTIONS` across all schemas — find any objects NOT in the predefined checklist
3. **Documentation drift:** Compare CLAUDE.md deployed objects table against actual live objects
4. **Dependency check:** Verify imports in Python files reference packages that exist
5. **Cross-reference:** Verify SQL scripts reference objects that actually exist in the live environment

For each discovered gap, create a finding. If 0 findings, mark `exploratory_sweep` as PASS.

## Agent Fallback Rules

- If `snowflake_sql_execute` fails with "terminated connection", use `snow sql -c se_demo -q "USE DATABASE APEX_CAPITAL_DEMO; <query>" --format json` via Bash
- If `python3 -m ruff` fails, report as SKIPPED (not FAIL) and continue
- If a file doesn't exist, report as SKIPPED for that file's checks
- Never halt the entire loop due to a single agent failure — mark that check as FAIL and continue to the next iteration

## Output

When the loop completes (convergence or max iterations), present:

```
# LoadStar Quality Report — Final

## Loop Summary
- Iterations: N
- Completion: CONVERGED | MAX_ITERATIONS
- Duration: [if tracked]

## Check Status
| Check | Status | Findings | Last Verified |
|-------|--------|----------|---------------|
| python_lint | PASS/FAIL | N | timestamp |
| ... | ... | ... | ... |

## Fixes Applied (cumulative)
[List all fixes from all iterations]

## Remaining Issues (if any)
[List any checks still failing]

## Lessons Learned (new this run)
[Any new patterns encoded into agents/PLAN.md]
```
