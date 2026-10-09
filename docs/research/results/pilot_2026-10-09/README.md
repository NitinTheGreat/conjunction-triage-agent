# First-cycle pilot evidence

These small CSV/JSON files are exact copies of completed local run artifacts.
`provenance.json` records their hashes, source run IDs, original manifest hashes
and source archive hashes. The findings are exploratory, not confirmation.

Regenerate into a new directory from the retained local runs:

```powershell
.\.venv\Scripts\python.exe -m research.export_pilot --output <new-directory>
```

Dataset files, models, predictions, logs, downloaded papers and machine/process
inventories are deliberately absent. A Git clone contains the readable results
and code; exact reconstruction still requires the source data and ignored
`processed/research/` artifacts identified in the checklist. Do not infer that
those files can be redistributed merely because a local run used them.
