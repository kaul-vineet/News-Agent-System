# News Agent System

Source-controlled Copilot Studio implementation of the BFSI news workflow.

## Components

| Component | Path | Tenant display name |
|---|---|---|
| Manifest agent | `agents/news-manifest-builder` | News Manifest Builder |
| Search agent | `agents/resilient-search-agent` | Resilient Search Agent |
| Summary agent | `agents/news-summary-agent` | News Summary Agent |
| Workflow solution | `solution` | News Agent Workflow |

## End-to-end flow

```text
Outlook email trigger
  -> News Manifest Builder
  -> SharePoint manifest JSON
  -> Resilient Search Agent loop
  -> one SharePoint consolidated JSON
  -> News Summary Agent
  -> deduplicated newsletter
  -> Outlook send
```

The workflow creates:

- `/Shared Documents/BFL Web Search/Inbound/<runId>_manifest.json`
- `/Shared Documents/BFL Web Search/Outbound/<runId>_consolidated.json`

## Repository layout

```text
agents/    Independent PAC Copilot Studio CLI projects
solution/  Unpacked Power Platform solution and workflow
shared/    Cross-component schemas and newsletter template
docs/      Architecture, deployment, and validation guidance
```

Tenant connection state under `.mcs` is intentionally excluded from source
control. Clone or initialize each agent locally before pulling or pushing.

## Current status

- All three tenant agents are represented as CLI-authoring projects.
- News Agent Workflow is unpacked from the solution ZIP.
- News Manifest Builder and Resilient Search Agent are deployed and working.
- News Summary Agent has the consolidated-JSON instructions and skill.
- The remaining full-flow work is documented in
  [`docs/deployment.md`](docs/deployment.md).
