# Architecture

## News Manifest Builder

Input:

- deterministic `runId`;
- Outlook connector message ID.

Behavior:

- reads the complete monitoring email;
- extracts every article-table row;
- assigns stable article identifiers;
- creates `<runId>_manifest.json` in the SharePoint Inbound folder; and
- returns the SharePoint file path and metadata.

It does not search articles or send email.

## Resilient Search Agent

Input:

- exactly one manifest item.

Behavior:

- runs in a fresh conversation for every article;
- searches only for the declared publisher;
- verifies the resolved article;
- returns compact article metadata, summary, facts, or an unresolved reason.

It does not create persistent per-article files or send email.

## News Agent Workflow

Behavior:

1. Triggers from the monitoring email.
2. Creates a deterministic `runId`.
3. Calls News Manifest Builder.
4. retrieves and parses the manifest from SharePoint.
5. Calls Resilient Search Agent sequentially for each manifest item.
6. Appends each parsed response to an in-memory array.
7. Creates one `<runId>_consolidated.json` file in SharePoint.
8. Calls News Summary Agent with only `runId`.

The workflow does not send the newsletter.

## News Summary Agent

Input:

- `runId`.

Behavior:

1. Reads `/Shared Documents/BFL Web Search/Outbound/<runId>_consolidated.json`.
2. Treats rows with a nonempty `resolvedUrl` as retrieved.
3. Preserves all other rows as unresolved accounting.
4. Analyzes and deduplicates retrieved rows by business event.
5. Selects one primary article per unique story.
6. Creates one executive line and one story card per story.
7. Renders the Outlook-safe HTML template.
8. Sends the newsletter once through the configured Outlook tool.

It does not read the original monitoring email, search the web, retrieve
publisher pages, create stories from unresolved rows, retry failed sends, or
use backup/fallback delivery paths.
