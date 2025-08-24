# Community Calendar Manager

A simple Streamlit app for reviewing submission to a community calendar.

Helps organizers review submissions to a Google Form, edit them, and publish them to a public calendar.

## Development

This repo uses [uv](https://docs.astral.sh/uv/) for package and environment management. With `uv` installed, run the app locally with

```bash
uv run streamlit run main.py
```

## Secrets

This project makes heavy use of [Streamlit secrets](https://docs.streamlit.io/develop/api-reference/connections/st.secrets) for configuration. Primary components include:

- `spreadsheet_id`: ID of the Google spreasheet linked to the submission form. The long string in the URL after "spreadsheets/d/".
- `calendar_id`: ID of the calendar. Looks like an email ending in "@group.calendar.google.com", unless it's the default calendar in which case it's just the email address of the account.
- `auth` section for Google
([Streamlit docs](https://docs.streamlit.io/develop/api-reference/user/st.login)).
  - This requires a web app set up in [Google Cloud](https://docs.streamlit.io/develop/tutorials/authentication/google).
  - Remember that the `redirect_uri` will be different in local development and in the deployed app, e.g. on Community Cloud, and both need to be registered on Google Cloud.
- `gcp_service_account` section containing the keys of a GCP service account (IAM & Admin > Service accounts > Manage keys).
  - The Google Calendar, Google Sheets, and Google Drive APIs will also have to be activated for the GCP project, and the service account added as an editor of the calendar and the response GSheet.

## Authorized Users

Emails of users authorized to process calendar submissions need to be in the Google Sheet on the Authorized Users sheet, which has columns for Name and Email. They must match the email returned when you log in with Google.
