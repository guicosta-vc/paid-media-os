# Agent Compatibility

Paid Media OS is a portable instruction and artifact package. It does not require a specific model or vendor, but an agent must be able to read local Markdown and JSON files and run Python 3.11 for the CLI.

## Common installation paths

- **Claude:** preserve each `skills/<name>/SKILL.md` folder and its linked files in the custom-skill location supported by your Claude environment. Start the conversation by attaching or referencing `AGENT_GUIDE.md` and the selected skill.
- **Hermes:** copy a selected skill folder into the active profile's skills directory, or keep this repository mounted and ask the agent to read the selected `SKILL.md` before operating. Do not install another team's private workspace.
- **ChatGPT Project or custom GPT:** paste the selected `SKILL.md` into instructions and upload its linked templates plus `AGENT_GUIDE.md` as project knowledge. Keep the workspace outside uploaded knowledge.
- **Other agents:** provide `AGENT_GUIDE.md`, the selected `SKILL.md`, its linked templates, and the exact CLI command. The workflow is not tied to a proprietary plugin format.

## Minimum capabilities

| Capability | Required for |
| --- | --- |
| Read Markdown and JSON | Every workflow |
| Run Python 3.11 | Workspace validation and CLI actions |
| Store a private local workspace | Any account-specific operation |
| Hold secrets outside repository files | Live Meta reads or writes |
| Obtain explicit human approval | Every external Meta write |

## Acceptance check

After installation, the agent should be able to do all of the following without network access:

```bash
python3 scripts/mos.py init --workspace ./workspace/demo
python3 scripts/mos.py validate --workspace ./workspace/demo
python3 -m unittest discover -s tests -v
```

The initial workspace intentionally fails validation until the operator replaces example asset and Meta identifiers with approved real values. This proves the workflow fails closed rather than treating examples as launch-ready.
