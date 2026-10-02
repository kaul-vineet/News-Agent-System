# News Agent System

Source-controlled Copilot Studio implementation of the BFSI news workflow.

## Components

| Component | Path | Tenant display name |
|---|---|---|
| Manifest agent | `agents/news-manifest-builder` | News Manifest Builder |
| Search agent | `agents/resilient-search-agent` | News Search Agent |
| Summary agent | `agents/news-summary-agent` | News Summary Agent |
| Workflow solution | `solution` | News Agent Workflow |

## End-to-end flow

```text
Outlook email trigger
  -> News Manifest Builder
  -> SharePoint manifest JSON
  -> News Search Agent loop
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
- News Manifest Builder is managed in the target tenant.
- News Search Agent is deployed and published.
- The News Summary Agent source defines one summary skill and exactly two tools:
  consolidated SharePoint read and Outlook send.
- Target deployment of News Summary Agent is pending recreation because the
  earlier solution import produced malformed skill and tool placeholders.
- News Agent Workflow invokes News Summary Agent after consolidated-file
  creation with connector retry disabled; its target reference must be verified
  after the Summary Agent is recreated.
