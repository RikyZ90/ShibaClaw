# Implementation Plan

[Overview]
Fix bugs in the automation functionality to ensure consistent behavior for job deletion and task extraction.

The current implementation of the `AutomationService` only respects the `delete_after_run` flag for one-shot (`at`) jobs, ignoring it for recurring jobs. Additionally, the `AutomationTool` used by the agent does not allow specifying whether a job should be deleted after its first run. This plan aims to unify the deletion logic and enhance the agent's ability to manage job lifecycles.

[Types]
No changes to type definitions are required.

[Files]
Modify existing files to implement the fixes.

- `shibaclaw/automation/service.py`: Update the job execution logic to handle `delete_after_run` for all job types.
- `shibaclaw/agent/tools/automation.py`: Update the tool parameters and execution logic to support `delete_after_run`.

[Functions]
Modify the following functions:

- `AutomationService._execute` (in `shibaclaw/automation/service.py`):
    - Remove the restriction that checks `job.schedule.kind == "at"` before checking `job.delete_after_run`.
    - Ensure any job with `delete_after_run=True` is removed from the jobs registry after successful or failed execution.
    - Keep the logic that disables `at` jobs that are NOT marked for deletion.

- `AutomationTool.parameters` (in `shibaclaw/agent/tools/automation.py`):
    - Add `delete_after_run` (boolean) to the properties of the tool's parameters.

- `AutomationTool.execute` (in `shibaclaw/agent/tools/automation.py`):
    - Accept the `delete_after_run` argument.
    - Pass this value to the `_add_job` method.

- `AutomationTool._add_job` (in `shibaclaw/agent/tools/automation.py`):
    - Use the passed `delete_after_run` value instead of hardcoding it to `True` only for `at` jobs.

[Classes]
No new classes are needed. Existing classes `AutomationService` and `AutomationTool` will be modified as described in the Functions section.

[Dependencies]
No new dependencies are required.

[Testing]
Verify the fixes using the existing test suite and new test cases.

- Update `tests/test_automation.py` to include a test case where a recurring job is created with `delete_after_run=True` and verify it is removed after execution.
- Verify that `at` jobs are still disabled if `delete_after_run` is `False`.

[Implementation Order]
1. Modify `shibaclaw/automation/service.py` to implement universal `delete_after_run` logic.
2. Modify `shibaclaw/agent/tools/automation.py` to expose `delete_after_run` to the agent.
3. Update `tests/test_automation.py` to validate the changes.
4. Run tests to confirm the fix.