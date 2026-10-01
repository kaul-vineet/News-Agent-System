# Deployment

## Agent projects

Each directory under `agents` is an independent Copilot Studio CLI project.
Connect it to the intended tenant agent before using `pac copilot pull`,
`pac copilot push`, or `pac copilot publish`.

Do not commit `.mcs` connection state.

## Power Platform solution

The unpacked solution under `solution` is the editable source for News Agent
Workflow. Repack it from the repository root with:

```powershell
pac solution pack `
  --folder .\solution `
  --zipfile .\EmailMessengerBFLVineet_1_0_0_1.zip `
  --packagetype Unmanaged
```

## Remaining full-flow setup

Configure these tools on News Summary Agent:

1. SharePoint Get file content using path.
2. Office 365 Outlook Send Email.
3. Administrator-controlled newsletter recipients.

Then update News Agent Workflow:

1. Add a News Summary Agent action after Create Consolidated Results JSON.
2. Pass only the output of Create runId:

   ```json
   {
     "runId": "<Create runId output>"
   }
   ```

3. Do not add another Outlook send action after the agent.
4. Handle `sent` and `blocked` as terminal outcomes.
5. Disable automatic retry after an ambiguous or failed send.

Publish only after the controlled-recipient validation succeeds.
