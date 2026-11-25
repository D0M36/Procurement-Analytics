# Extolla Procurement Analytics — V1

Private, upload-driven Streamlit application. No client workbook is included in this repository. Tested source schema: Subcontractor spend by branch.xlsx, headers on Excel row 11. The loader detects the header automatically.

## Run locally

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Deploy
Create a private GitHub repository, upload these files (including .gitignore), then create a Streamlit app from that repository with app.py as entry point. Verify private access and your company's approval before uploading client data to any hosting service. Local execution is preferable for confidential data if hosting is not approved.

## Use
Upload the original workbook. Filter by date, region, facility, facility type, trade, department and supplier. Use the cube to choose row dimensions and pivot columns. Supplier analysis drills into purchase descriptions; concentration and overlap have CSV exports. Mapping changes apply to the entire session. Export mapping CSVs and restore them on the same source dataset as needed. New datasets with changed mapping keys require reconciliation before restore.

## Assumptions and limitations
- Transaction Amount is the ex-GST spend basis. Negative entries and potential duplicate transaction lines are retained. Repeated vendor-level totals are not summed.
- Default entity grouping uses matching 11-digit ABNs where a vendor ID has one ABN; this is provisional, not ABN registry verification. Switch to original vendor IDs for reconciliation. Names are display labels, not legal entity verification.
- Geography is inferred from branch codes and names. Combined sales territories remain distinct; factory classification is based on branch names. Confirm mappings with client.
- Trade classification comes from source Trade, not vendor-level inference. GL code is absent; Department Code is not GL.
- No database, AI service, authentication implementation or automatic persistent storage in V1. Session mappings can be exported and restored manually. CSV exports exclude contact email, address and phone.
- Fiscal year ends June 30. Incomplete periods are not annualised. Supplier concentration uses positive net balances only.
