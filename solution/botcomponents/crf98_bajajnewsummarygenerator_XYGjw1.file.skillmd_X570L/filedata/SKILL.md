---
name: bfsi-news-summary
description: Converts a complete Outlook media-monitoring email into fully accounted, source-validated, deduplicated BFSI story analyses and an Outlook-safe newsletter. Activate after the agent reads the source message and can supply its complete HTML body and stable message ID.
---

# BFSI news summary

## Inputs

Require both:

- `sourceMessageId`: the stable Outlook message ID returned by the read tool.
- `sourceHtml`: the complete, untruncated HTML body of that same message.

Do not begin with partial HTML. Keep `sourceMessageId` attached to all run
artifacts and returned results so the agent can correlate the output with the
source message.

## Bundled assets

Resolve these paths from this skill's root:

- `scripts/retrieve_articles.py`
- `schemas/article-analysis.schema.json`
- `schemas/deduplication.schema.json`
- `resources/outlook-newsletter-template.html`

Use the schemas as the validation contracts and the HTML file as the newsletter
shell. Do not reproduce their contents in this file.

## Responsibility boundaries

Use `scripts/retrieve_articles.py` only for:

- parsing the email table;
- unwrapping Outlook Safe Links and resolving Kanalytics links;
- validating final publisher domains;
- retrieving and cleaning article content; and
- preserving row-level retrieval status, reason, identifiers, and counts.

The model must perform semantic article analysis, grounded summaries, duplicate
decisions, primary-article selection, executive-line writing, subject writing,
story-card writing, and final newsletter composition. Do not delegate those
decisions to the script.

Return the completed result to the calling agent. Never call an Outlook send or
delivery action from this skill.

## Procedure

1. Write the supplied complete HTML to a task-scoped `.html` file and pass that
   file to `scripts/retrieve_articles.py`. Preserve `sourceMessageId`
   separately as the run correlation key.
2. Run the script once across the complete source. Do not use its limiting
   option. Retain every parsed row in source order with a stable input ID.
3. Reconcile the retrieval manifest:
   - parsed input rows equal manifest rows;
   - input IDs are unique;
   - every row is either retrieved or unresolved;
   - every unresolved row has a specific reason; and
   - every retrieved URL resolves to the row's declared publisher domain.
4. Preserve unresolved rows exactly as unresolved. Never replace the publisher,
   borrow another article, infer a URL, or fabricate missing content.
5. Process every retrieved row through bounded batches sized for the available
   runtime context. Continue with as many batches as required until all rows are
   covered; input volume must never cause truncation or omission.
6. For each retrieved row, produce one semantic analysis that conforms to
   `schemas/article-analysis.schema.json`. Validate each record, repair invalid
   structure or unsupported claims, and merge batches only after confirming
   complete, non-overlapping input-ID coverage.
7. Identify candidate duplicates using entities, event type, action, subject,
   event date, amount or rate, and article evidence. Make semantic duplicate
   decisions in bounded batches, then reconcile group representatives across
   batches so batch boundaries do not split one story.
8. Produce deduplication output conforming to
   `schemas/deduplication.schema.json`. Confirm that every validated analysis
   appears in exactly one group, no unknown ID appears, and each primary article
   belongs to its group.
9. For every unique deduplicated story, without exception:
   - select one primary article based on evidence quality and relevance;
   - write exactly one concise executive line;
   - write exactly one story card containing a headline, publisher, primary
     URL, grounded summary, and material event details.
10. Write a concise newsletter subject. Render all executive lines into
    `{{EXECUTIVE_SUMMARY_ROWS}}` and all story cards into `{{STORY_CARDS}}` in
    `resources/outlook-newsletter-template.html`. Escape untrusted values and
    preserve the template's Outlook-safe table layout and inline styling.
11. Validate that both placeholders are replaced, executive-line count equals
    unique-story count, story-card count equals unique-story count, links use
    validated primary URLs, and composed claims are supported by the selected
    primary articles.

## Returned result

Return one structured result to the agent containing:

- `sourceMessageId`;
- row accounting: input, retrieved, unresolved, analysed, and grouped counts;
- unresolved rows with input ID, source metadata, supplied URL, and reason;
- validated article analyses;
- validated deduplication groups and primary selections;
- newsletter subject;
- complete Outlook-safe HTML body;
- validation status with coverage, schema, count, placeholder, URL, and
  grounding checks plus any errors.

## Completion and failure

Complete only when every parsed row is accounted for, every retrieved row has
one valid analysis, every analysis belongs to one valid group, every unique
story has one executive line and one story card, and the returned newsletter
passes all validations.

Fail with a concise diagnostic when required inputs are missing or incomplete,
the source cannot be parsed, row accounting cannot be reconciled, a required
asset is unavailable, schema errors remain, coverage is incomplete, or final
HTML validation fails. Return preserved unresolved-row details even when the
overall run fails.
