# Ausco Procurement Analytics V3
Replace app.py, rebate.py, requirements.txt and .gitignore in your existing app repository. Do not commit the original workbook or secrets to a public repository.

## Automatic workbook loading on Streamlit Cloud
1. Create a separate **private** GitHub repository named `Ausco-Data` (only if approved for the client data). Upload `Subcontractor spend by branch.xlsx` there, at the root. Verify the repository is private.
2. Create a fine-grained GitHub personal access token restricted to Ausco-Data, with Contents read-only permission and an expiry. Do not share it or commit it.
3. In the Streamlit app settings, open Secrets and enter the following (replace placeholders):

```toml
APP_PASSWORD = "YOUR-EXISTING-PASSWORD"
DATA_REPO = "YOUR-GITHUB-USERNAME/Ausco-Data"
DATA_PATH = "Subcontractor spend by branch.xlsx"
DATA_TOKEN = "YOUR-READ-ONLY-TOKEN"
```

Save and reboot the app. The login appears before the workbook is fetched; after login, the original data loads automatically. An optional replacement uploader remains available. For local hosting, put the workbook under `data/` beside app.py and set APP_PASSWORD in `.streamlit/secrets.toml` instead. The public code package does not include the workbook or password. The requested shared password is weak and should be changed before production use; a private app with individual authentication is preferable. Verify client cloud-hosting permission and access controls before using real data.

Numeric tables use centered numeric columns with locale-aware thousands separators and percentage formatting for share columns. CSV exports retain raw numeric values (shares are fractions for calculation). Mapping changes remain session-only. Syntax checked; live Streamlit deployment and browser rendering not tested.

## Rebate analysis
Select Rebate analysis in the sidebar. The default baseline is 1 January 2025 inclusive to 1 January 2026 exclusive, on both the general dashboard and rebate page. Dates can be changed. Rates and thresholds can be edited and applied; export or restore the CSV to preserve changes between sessions. National annual supplier/trade spend determines retrospective rates; selected regional and facility spend is allocated at those rates. The global posting date range is ignored on this page. Non-annual periods are not annualised. Existing mapping assumptions, credits and duplicate treatment are unchanged. All rates are proposed targets.
