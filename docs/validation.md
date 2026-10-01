# Validation

Use a two-article email before a production-volume run.

## Upstream workflow

- The same source email produces the same `runId`.
- Exactly one manifest JSON is created.
- The manifest contains the expected number of rows.
- Every loop iteration sends one article to a fresh search conversation.
- Exactly one consolidated JSON is created.
- No per-article SharePoint result files are created.
- The consolidated file is a valid nonempty JSON array.

## Summary agent

- The agent receives only `runId`.
- It reads the matching consolidated file from SharePoint.
- It does not read the source email or perform web search.
- Retrieved and unresolved counts match the array contents.
- Duplicate coverage becomes one business story.
- Every unique story has one executive line and one story card.
- Every newsletter link comes from the selected result's `resolvedUrl`.
- The HTML template has no unreplaced placeholders or active content.

## Delivery

- A pending ledger entry exists before Outlook send.
- A successful send updates the ledger to sent.
- Repeating the same `runId` returns `already_sent`.
- Pending or ambiguous ledger state returns `blocked`.
- Only the administrator-configured validation recipient receives the test.
- The workflow does not send a second email.

