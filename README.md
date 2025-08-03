# Community Calendar Manager

A simple Streamlit app for reviewing submission to a community calendar.

Helps organizers review submissions to a Google Form, edit them, and publish them to a public calendar.

## Development

This repo uses [uv](https://docs.astral.sh/uv/) for package and environment management. With `uv` installed, run the repo locally with

```bash
uv run streamlit run main.py
```

## Secrets

This project makes heavy use of [Streamlit secrets](https://docs.streamlit.io/develop/api-reference/connections/st.secrets) for configuration. Primary components include:

- `spreadsheet_id`: ID of the Google spreasheet linked to the submission form. The long string in the URL after "spreadsheets/d/". The spreadsheet and calendar must be shared with the service account used.
- `calendar_id`: ID of the calendar. Looks like an email ending in "@group.calendar.google.com".
- `auth` section for Google ([Streamlit docs](https://docs.streamlit.io/develop/api-reference/user/st.login))
- `gcp_service_account` section containing the keys of a GCP service account (IAM & Admin > Service accounts > Manage keys).
