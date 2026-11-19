---
name: "guide-me"
description: "Guide a user through the spec-driven development lifecycle. Create tasks, implemenet them, test, resolving failures, detecting and accepting drift and making a pull-request. Make use of agent skills to implement process."
metadata:
  author: "neoformit"
---

The user is assumed to be a junior developer, who needs to be walked through the process of working with spec-driven development with an agent. The steps below are not for you to do, they are for you to prompt the user, and they should carry out these steps in a separate session. At the end of this process, they should have learned enough to do spec-driven develpoment without this guide.

docs/images/dev-lifecycle.png illustrates the lifecycle - you may wish to nudge the user towards this before starting.

Prompt the user to start a new session to clear context between task creation and implementation.

When giving instruction, prompt the user to return to your session once the current step is complete.

## Steps

1. An issue is created in GitHub (or pick an existing one - look for label `agent-ready` for something that an agent can do autonomously)
2. Agent: Run `/speckit-tasks for issue #123` to create a task from the issue. For testing, agent unit/integration tests and manual nf-test review is usually the right choice.
3. Review the task brief for correctness, and commit to main. Let the user know that the task brief is often large, and is usually skim-read for important parts - approach and intended functionality.
4. Agent: Run `/speckit-implement <task_number>` to start the task. It will create its own branch in a worktree.
5. Review output - ensure that tests are passing and there are no outstanding problems. Out-of-scope issues should be appended to todo.md.
6. Ask the agent to create a PR
7. PR should trigger a docker image build, then nf-test workflow
8. Check that all tests are passing, and PR has been approved by Cam/Magda
9. Merge the PR
10. Git pull `main`
11. Cleanup - ensure that task is marked complete, is removed from active.md, and the worktree and branch have been cleaned up.

## Failed nf-test

Test failures are usually caused by drift (small changes in API data), and it
can be a little tricky to tell this apart from real bugs. If a bug is found, fix
and push. When no bugs remain, you can accept drift by promoting fixures for nf-test and/or Selenium.

### nf-test

1. On GitHub, review the nf-test diff in the workflow run.
2. The main thing to check is that none of the samples actually failed the run - that's a clear indication of a bug.
3. File diffs are hash-based, and will only show that a file has changed. You'll need to SSH into the runner to check what the actual change in the file was, and decide if it indicates drift or a bug.
4. Run `/investigate-runner <runner_path> - sample <sample_id> failed nf-test diff on file XXX please check this output for potential bugs`. There is no 'expected' file to compare to (just a checksum), so it's not possible to tell what the diff was.
5. If satisfied that the diff indicates no bugs, you can accept it on the runner:
   `cd <TEST_DIR> && nf-test test --update-snapshot`

### Selenium tests

1. If the workflow has failed in GitHub actions, download the review.html artifact. This contains a summary of the Selenium test diffs.
2. Open review.html and review the diff. Each diff is either "drift" (harmless, minor movement in external data) or indicates a bug. A number changing by 10-20% is usually drift. If you have made deliberate changes to GBIF/Genbank API modules, you might expect to see larger changes.
3. If you identify a bug, investigate it to confirm. Use `/investigate-runner <runner_path> - sample <sample_id> has failed with <paste_table_row>`
4. For big diffs, you can also use `/selenium-review <review_json_path>` to get the agent to review the diff for you. You can provide runner SSH command and runner path to allow it to investigate the workdir.
5. If a bug is identified, ask the agent to fix it (write a task if it's a big fix) and push to the PR.
6. Repeat the process until the tests pass, or selenium diff all looks like drift.
7. To accept drift, run `venv/bin/python testkit.py promote --all --yes -d <reports_dir>` in `tests/selenium` . This will update the fixtures so the next test passes cleanly. DO NOT RUN THIS UNTIL BUGS ARE FIXED!
8. Push to the PR branch. Tests should pass, and the PR can be merged.
