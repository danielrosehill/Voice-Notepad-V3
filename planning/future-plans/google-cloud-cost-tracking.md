# Google Cloud Cost Tracking - Reference Notes

## Summary

**Not implementing** - too complex for the benefit.

## Why It's Complex

Google Cloud does not provide a simple API to fetch actual spending. The options are:

1. **BigQuery Billing Export** - Requires setting up export to BigQuery, then querying BigQuery. Overkill for this app.

2. **Cloud Billing API** - Only provides:
   - Billing account listing
   - SKU pricing info
   - Cost estimation (not actual spend)

3. **Budget API** - For setting budgets and alerts, not retrieving historical costs.

## Key Limitations

- Cannot track at API key level
- Project-level only (includes all services, not just Gemini)
- Requires separate authentication (service account or OAuth)

## Current Approach

The app estimates costs based on token usage reported in API responses. This is sufficient for most use cases and doesn't require additional setup.
