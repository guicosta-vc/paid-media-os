# Agent Compatibility

Paid Media OS is a portable instruction and artifact package. It does not require a specific model or vendor, but an agent must be able to read local Markdown and JSON files and run Python 3.11 for the CLI.

## Installation contract

Install the **complete repository** or create a complete local bundle:

```bash
python3 scripts/mos.py install-bundle --destination /private/path/paid-media-os
```

A standalone `skills/<name>` folder is intentionally insufficient for execution because the skills share the CLI, templates, safety policy, and implementation guide. Keep all bundle files together and create tenant workspaces outside the repository or bundle.

## Common agent handoffs

- **Claude:** make the full repository or portable bundle available in the workspace. Start by attaching or referencing `AGENT_GUIDE.md`, then direct Claude to the relevant skill.
- **Hermes:** keep the complete repository or bundle mounted and direct Hermes to read `AGENT_GUIDE.md` and the relevant `skills/<name>/SKILL.md`. If installing a native skill folder, retain a path to the complete bundle for its shared dependencies.
- **ChatGPT Project or custom GPT:** upload or attach `AGENT_GUIDE.md`, the relevant skill, and the specific supporting templates; keep credentials and private workspaces outside uploaded project knowledge. Use a local runner for CLI actions.
- **Other agents:** provide `AGENT_GUIDE.md`, the relevant `SKILL.md`, its supporting templates, and the exact CLI command. The workflow is not tied to a proprietary plugin format.

## Minimum capabilities

- Read Markdown and JSON.
- Run Python 3.11 for workspace validation and CLI actions.
- Store a private local workspace for account-specific operations.
- Hold secrets outside repository files.
- Obtain explicit human approval for every external Meta write.

## Offline acceptance check

After installation, the agent should be able to run:

```bash
python3 scripts/mos.py init --workspace ./workspace/demo
python3 scripts/mos.py validate --workspace ./workspace/demo
python3 -m unittest discover -s tests -v
```

The initial workspace intentionally fails validation until the operator completes all gates: tenant lifecycle, Strategy Lock approval, 50-concept register, 3-5-concept selection, approved production register, catalog, and scope. This proves the workflow fails closed rather than treating examples as launch-ready.
