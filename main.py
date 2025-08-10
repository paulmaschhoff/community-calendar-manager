import re
from datetime import datetime
from urllib.parse import quote_plus

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# Scopes required for Google Sheets access
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/calendar',
]


class FIELDS:
    """
    Class to hold field names for the Google Sheets data.
    """

    EVENT_NAME = 'Event Name'
    DESCRIPTION = 'Description'
    EVENT_DATE = 'Event Date'
    END_DATE = 'End Date'
    START_TIME = 'Start Time'
    END_TIME = 'End Time'
    LOCATION = 'Location'
    EVENT_TYPE = 'Event Type'
    ORG_NAME = 'Organization Name'
    PHONE = 'Contact Phone Number'
    FEE = 'Fee'
    EMAIL = 'Email Address'
    STATUS = 'Status'
    LAST_UPDATED_BY = 'Last Updated By'


REQUIRED_FIELDS = [
    FIELDS.EVENT_NAME,
    FIELDS.LOCATION,
    FIELDS.DESCRIPTION,
    FIELDS.ORG_NAME,
    FIELDS.EVENT_TYPE,
    FIELDS.FEE,
    FIELDS.EVENT_DATE,
    FIELDS.EMAIL,
]

OPTIONAL_FIELDS = [
    FIELDS.START_TIME,
    FIELDS.END_TIME,
    FIELDS.END_DATE,
]


@st.cache_resource
def get_google_sheets_client():
    """
    Create and cache a Google Sheets client using service account credentials.

    Returns
    -------
    gspread.Client
        An authorized gspread client for Google Sheets access.
    """
    try:
        # Get service account info from secrets
        service_account_info = st.secrets['gcp_service_account']

        # Create credentials from the service account info
        credentials = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)

        # Create and return the gspread client
        client = gspread.authorize(credentials)
        return client

    except Exception as e:
        st.error('Failed to authenticate with Google Sheets:')
        st.exception(e)
        st.stop()


def ensure_status_columns(spreadsheet_id, worksheet_name='Form Responses 1'):
    """
    Check if Status and Last Updated By columns exist, add them if they don't.

    Parameters
    ----------
    spreadsheet_id : str
        The ID of the Google Spreadsheet.
    worksheet_name : str, optional
        Name of the worksheet (default is 'Form Responses 1').

    Returns
    -------
    None
        Adds columns if missing; reruns Streamlit app if changes are made.
    """
    client = get_google_sheets_client()
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name)

    # Get the header row
    headers = worksheet.row_values(1)

    # Add any missing required columns
    missing_cols = [col for col in [FIELDS.STATUS, FIELDS.LAST_UPDATED_BY] if col not in headers]
    if len(missing_cols) == 0:
        return
    for col_idx, col in enumerate(missing_cols, start=1 + len(headers)):
        worksheet.update_cell(1, col_idx, col)
        st.success(f"Added '{col}' column to the spreadsheet")
    st.cache_data.clear()  # Clear cache to reflect changes
    st.rerun()  # Rerun to reflect changes immediately


@st.cache_data(ttl=300, show_spinner=False)  # Cache for 5 minutes
def load_spreadsheet_data(spreadsheet_id, worksheet_name='Form Responses 1'):
    """
    Load data from a Google Spreadsheet, filtering out ignored/completed items.

    Parameters
    ----------
    spreadsheet_id : str
        The ID of the Google Spreadsheet.
    worksheet_name : str, optional
        Name of the worksheet to load (default is 'Form Responses 1').

    Returns
    -------
    pandas.DataFrame
        The spreadsheet data as a DataFrame, filtered for display.
    """
    try:
        # Get the Google Sheets client
        client = get_google_sheets_client()

        # Open the spreadsheet by ID
        spreadsheet = client.open_by_key(spreadsheet_id)

        # Get the specified worksheet
        worksheet = spreadsheet.worksheet(worksheet_name)

        # Load all records into a DataFrame
        df = pd.DataFrame(worksheet.get_all_records())

        if not df.empty:
            # Filter out ignored and completed submissions
            df = df[~df['Status'].isin(['Ignored', 'Added to Calendar'])]

            # Filter out columns that are not needed for display
            df = df.drop(columns=[FIELDS.STATUS, FIELDS.LAST_UPDATED_BY], errors='ignore')

        return df

    except gspread.SpreadsheetNotFound:
        st.error('Spreadsheet not found. Please check the spreadsheet ID.')
        st.stop()
    except gspread.WorksheetNotFound:
        st.error(f"Worksheet '{worksheet_name}' not found in the spreadsheet.")
        st.stop()
    except Exception as e:
        st.error('Error loading spreadsheet data:')
        st.exception(e)
        st.stop()


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_authorized_users(spreadsheet_id: str) -> set:
    """
    Get the list of authorized users from the spreadsheet.

    Parameters
    ----------
    spreadsheet_id : str
        The ID of the Google Spreadsheet.

    Returns
    -------
    set
        Set of authorized user email addresses.
    """
    worksheet_name = 'Authorized Users'
    try:
        client = get_google_sheets_client()
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)

        # Get all records
        records = worksheet.get_all_records()

        # Extract unique usernames from 'Email' column
        usernames = set(record.get('Email') for record in records)

        return usernames

    except Exception as e:
        st.error('Error retrieving authorized users:')
        st.exception(e)
        return set()


def update_submission_status(
    spreadsheet_id: str, row_idx: int, status: str, worksheet_name: str = 'Form Responses 1'
):
    """
    Update the status of a submission in the spreadsheet.

    Parameters
    ----------
    spreadsheet_id : str
        The ID of the Google Spreadsheet.
    row_idx : int
        Row index in the original sheet (0-indexed, not counting header).
    status : str
        New status to set.
    worksheet_name : str, optional
        Name of the worksheet (default is 'Form Responses 1').

    Returns
    -------
    bool
        Success status.
    """
    try:
        client = get_google_sheets_client()
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)

        # Get headers to find Status column
        headers = worksheet.row_values(1)
        status_col = headers.index('Status') + 1
        last_updated_col = headers.index('Last Updated By') + 1

        # Update status
        row_num = row_idx + 2  # Convert to 1-based index for Google Sheets
        worksheet.update_cell(row_num, status_col, status)

        # Update last updated by
        worksheet.update_cell(row_num, last_updated_col, st.user.name)  # type: ignore

        # Clear cache to reflect changes
        st.cache_data.clear()
        return True

    except Exception as e:
        st.error('Error updating submission status:')
        st.exception(e)
        return False


@st.cache_resource
def get_google_calendar_service():
    """
    Create and cache a Google Calendar service using service account credentials.

    Returns
    -------
    googleapiclient.discovery.Resource
        An authorized Google Calendar API service resource.
    """
    try:
        service_account_info = st.secrets['gcp_service_account']
        credentials = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        from googleapiclient.discovery import build

        service = build('calendar', 'v3', credentials=credentials)
        return service
    except Exception as e:
        st.error('Failed to authenticate with Google Calendar:')
        st.exception(e)
        st.stop()


def add_event_to_calendar(event_data: dict):
    """
    Add an event to the Google Calendar using the provided event data.

    Parameters
    ----------
    event_data : dict
        Dictionary containing event details.

    Returns
    -------
    bool
        Success status.
    """
    event: dict = dict(
        summary=event_data[FIELDS.EVENT_NAME],
        location=event_data[FIELDS.LOCATION],
        description=format_description(event_data),
    )
    tz = {'timeZone': 'America/Chicago'}
    if event_data[FIELDS.START_TIME] is None:
        event['start'] = {'date': event_data[FIELDS.EVENT_DATE].isoformat()}
        event['end'] = {'date': event_data[FIELDS.END_DATE].isoformat()}
    else:
        event['start'] = dict(
            dateTime=f'{event_data[FIELDS.EVENT_DATE].isoformat()}T{event_data[FIELDS.START_TIME].isoformat()}',
            **tz,
        )
        event['end'] = dict(
            dateTime=f'{event_data[FIELDS.END_DATE].isoformat()}T{event_data[FIELDS.END_TIME].isoformat()}',
            **tz,
        )

    if (calendar_id := st.secrets.get('calendar_id')) is None:
        st.error('Calendar ID not found in secrets. Please add it to .streamlit/secrets.toml')
        return False
    try:
        service = get_google_calendar_service()
        service.events().insert(calendarId=calendar_id, body=event).execute()
        return True
    except Exception as e:
        st.error(
            'Error adding event to calendar: Please make sure the calendar ID '
            f'({calendar_id}) is correct and that the service account '
            f'({st.secrets.gcp_service_account.client_email}) has permission to write to it.'
        )
        st.exception(e)
        return False


def format_description(event_data: dict) -> str:
    """
    Format the event description as HTML.

    Parameters
    ----------
    event_data : dict
        Dictionary containing event details.

    Returns
    -------
    str
        HTML-formatted event description.
    """
    return (
        f'<p>{event_data[FIELDS.DESCRIPTION]}</p>'
        f'<p><strong>Submitter:</strong> {event_data[FIELDS.ORG_NAME]}<br>'
        f'<strong>Event Type:</strong> {event_data[FIELDS.EVENT_TYPE]}<br>'
        f'<strong>Fee:</strong> {event_data[FIELDS.FEE]}<br>'
        f'<strong>Email:</strong> {event_data[FIELDS.EMAIL]}</p>'
    )


def show_field_editor(field_name: str, event_data: dict):
    """
    Display an editor widget for a specific field in the event data. The data is updated in-place.

    Parameters
    ----------
    field_name : str
        The name of the field to edit.
    event_data : dict
        The event data dictionary to update.

    Returns
    -------
    None
    """
    value = event_data[field_name]
    if field_name in (FIELDS.START_TIME, FIELDS.END_TIME):
        if value == '':
            value = None
        elif isinstance(value, str):
            # Convert string to time for st.time_input
            value = pd.to_datetime(value).time()
        event_data[field_name] = st.time_input(field_name, value=value)
    elif field_name in (FIELDS.EVENT_DATE, FIELDS.END_DATE):
        # Convert string to date for st.date_input
        if field_name == FIELDS.END_DATE and value == '':
            value = event_data[FIELDS.EVENT_DATE]
        else:
            value = datetime.strptime(str(value), '%m/%d/%Y')
        event_data[field_name] = st.date_input(field_name, value=value, format='MM/DD/YYYY')
    elif field_name == FIELDS.DESCRIPTION:
        event_data[field_name] = st.text_area(
            field_name,
            value=value,
            help='This free-text description will be combined with the structured data to create '
            'the full formatted event description.',
        )
    else:
        event_data[field_name] = st.text_input(field_name, value=value)


def show_event_editor(event_data: dict):
    """
    Display an editor for all event fields and return the edited event data.

    Parameters
    ----------
    event_data : dict
        The event data dictionary to edit.

    Returns
    -------
    dict
        The edited event data.
    """
    event_data = event_data.copy()
    show_field_editor(FIELDS.EVENT_NAME, event_data)
    with st.container(horizontal=True, vertical_alignment='bottom'):
        show_field_editor(FIELDS.LOCATION, event_data)
        st.link_button(
            'Search Google Maps',
            url=f'https://www.google.com/maps/search/{quote_plus(event_data[FIELDS.LOCATION])}',
            help='For addresses, search on Google Maps',
        )
        url = event_data[FIELDS.LOCATION]
        st.link_button(
            'Open URL',
            url=url if url.startswith('http://') else f'https://{url}',
            help='For URLs, open in a new tab',
        )
    show_field_editor(FIELDS.DESCRIPTION, event_data)
    col1, col2 = st.columns(2)
    with col1:
        show_field_editor(FIELDS.ORG_NAME, event_data)
        show_field_editor(FIELDS.EVENT_TYPE, event_data)
    with col2:
        show_field_editor(FIELDS.EMAIL, event_data)
        show_field_editor(FIELDS.FEE, event_data)

    date1, time1, date2, time2 = st.columns(4)
    st.write(
        'All-day events should have `Start Time` and `End Time` left empty and may span multiple days. '
        'All events are assumed to be in the Central Time Zone (America/Chicago).'
    )
    with date1:
        show_field_editor(FIELDS.EVENT_DATE, event_data)
    with time1:
        show_field_editor(FIELDS.START_TIME, event_data)
    with date2:
        show_field_editor(FIELDS.END_DATE, event_data)
    with time2:
        show_field_editor(FIELDS.END_TIME, event_data)

    return event_data


def validate_event_data(event_data: dict) -> bool:
    """
    Validate the event data for required fields and logical consistency.

    Parameters
    ----------
    event_data : dict
        The event data dictionary to validate.

    Returns
    -------
    bool
        True if the event data is valid, False otherwise.
    """
    errors = []
    warnings = []

    # Check that the event data contains all required fields
    for field in REQUIRED_FIELDS:
        if not event_data.get(field):
            errors.append(f"The field '{field}' is required and cannot be empty.")

    # Validate date and time fields
    if event_data[FIELDS.END_DATE] < event_data[FIELDS.EVENT_DATE]:
        errors.append('End Date cannot be earlier than Event Date.')
    elif event_data[FIELDS.END_DATE] > event_data[FIELDS.EVENT_DATE]:
        if event_data[FIELDS.START_TIME] is not None or event_data[FIELDS.END_TIME] is not None:
            warnings.append('Start and end times are ignored for multi-day events.')
    elif event_data[FIELDS.START_TIME] is not None or event_data[FIELDS.END_TIME] is not None:
        if event_data[FIELDS.START_TIME] is None:
            errors.append('If End Time is set, Start Time must also be set.')
        elif event_data[FIELDS.END_TIME] is None:
            errors.append('If Start Time is set, End Time must also be set.')
        elif event_data[FIELDS.END_TIME] < event_data[FIELDS.START_TIME]:
            errors.append('End Time must be after Start Time.')

    # Validate email format
    email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,6}$'
    if not re.match(email_pattern, event_data[FIELDS.EMAIL]):
        errors.append(
            f"Email '{event_data[FIELDS.EMAIL]}' is not valid. Please enter a valid email address."
        )

    # Show warnings and errors
    if len(warnings) > 0:
        for warning in warnings:
            st.warning(warning)
    if len(errors) > 0:
        for error in errors:
            st.error(error)
        return False

    return True


def show_header(spreadsheet_id: str):
    """
    Display the header with a link to the Google Sheet and a refresh button.

    Parameters
    ----------
    spreadsheet_id : str
        The ID of the Google Spreadsheet.

    Returns
    -------
    None
    """
    st.write(f'Hello, {st.user.name}!')

    # Add link to sheet and refresh button at the top
    with st.container(horizontal=True):
        sheet_url = f'https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit'
        st.link_button('Form Responses GSheet', url=sheet_url, icon=':material/open_in_new:')
        if st.button('🔄 Refresh Data', help='Re-load the data from the GSheet.'):
            st.cache_data.clear()
            st.rerun()
        with st.container(horizontal_alignment='right'):
            if st.button('Log out'):
                st.logout()


# Main application
def main():
    """
    Main entry point for the Streamlit application.

    Returns
    -------
    None
    """
    st.title('Form Submission Review')

    if not st.user.is_logged_in:
        if st.button('Log in'):
            st.login()
        st.stop()

    # Get spreadsheet ID from secrets
    if (spreadsheet_id := st.secrets.get('spreadsheet_id')) is None:
        st.error('`spreadsheet_id` not found in secrets. Please add it to .streamlit/secrets.toml')
        st.stop()

    show_header(spreadsheet_id)

    if st.user.email not in get_authorized_users(spreadsheet_id):
        st.error(
            f'Your email ({st.user.email}) is not in the list of authorized users. '
            'Please check the Authorized Users sheet in the form responses spreadsheet.'
        )
        st.stop()

    # Ensure Status column exists
    ensure_status_columns(spreadsheet_id)

    # Load and display submissions
    st.header('Pending Submissions')

    with st.spinner('Loading submissions...'):
        submissions = load_spreadsheet_data(spreadsheet_id)

    if submissions.empty:
        st.info('No pending submissions to review.')
        st.stop()

    st.success(f'Loaded {len(submissions)} pending submissions')

    # Display the dataframe with row selection
    dataframe_state = st.dataframe(
        submissions.rename(columns={'Timestamp': 'Submission Time'}),
        use_container_width=True,
        on_select='rerun',
        selection_mode='single-row',
        hide_index=True,
    )

    # Check that all expected columns are present
    missing_columns = [
        col for col in REQUIRED_FIELDS + OPTIONAL_FIELDS if col not in submissions.columns
    ]
    if len(missing_columns) > 0:
        st.error(
            f'The following required columns are missing from the spreadsheet: {", ".join(missing_columns)}'
        )
        st.stop()

    # Handle row selection
    if len((rows := dataframe_state.selection.rows)) > 0:  # type: ignore
        selected_row = submissions.iloc[rows[0]]

        st.divider()
        st.subheader('Edit Submission Details')

        # Create editable fields for the selected submission
        edited_data = show_event_editor(selected_row.to_dict())
        if not validate_event_data(edited_data):
            st.stop()

        with st.expander('Formatted Description', expanded=True):
            st.html(format_description(edited_data))

        # Action buttons
        with st.container(horizontal=True):
            if st.button('🚫 Mark as Ignored', type='secondary'):
                # Find original row index
                if update_submission_status(spreadsheet_id, selected_row.name, 'Ignored'):
                    st.success(f"Marked '{edited_data[FIELDS.EVENT_NAME]}' as ignored")

            if st.button('📅 Add to Calendar', type='primary'):
                if add_event_to_calendar(edited_data):
                    if update_submission_status(
                        spreadsheet_id, selected_row.name, 'Added to Calendar'
                    ):
                        st.success(f"Added '{edited_data[FIELDS.EVENT_NAME]}' to calendar!")
                else:
                    st.error('Failed to add event to calendar.')

    else:
        st.info(
            'Select a row from the table above to review and edit the submission.',
            icon=':material/arrow_upward:',
        )


if __name__ == '__main__':
    main()
