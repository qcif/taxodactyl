# Instructions for agents

Before doing anything, check what branch you're on. Don't assume you're on main.

Before running python code, run `source scripts/venv/bin/activate` to obtain required environment variables and activate the virtual environment.

For running units tests, you can find instructions for doing so in ./.vscode/launch.json.

When I ask you to run integration tests, you can find instructions for doing so in ./.vscode/launch.json.

For interacting with Azure, please `source deployment/azure/batch-helpers.sh` and reference the docs in docs/azure.

If you edit nextflow code (*.nf) you should lint it with `nextflow lint <file>`.
