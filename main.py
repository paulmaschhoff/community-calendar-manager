import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# Scopes required for Google Sheets access
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/calendar',
]


@st.cache_resource
def get_google_sheets_client():
    """
    Create and cache a Google Sheets client using service account credentials
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
    Check if Status column exists, add it if it doesn't

    Args:
        spreadsheet_id (str): The ID of the Google Spreadsheet
        worksheet_name (str): Name of the worksheet

    Returns:
        int: Column index of the Status column (1-indexed)
    """
    client = get_google_sheets_client()
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name)

    # Get the header row
    headers = worksheet.row_values(1)

    # Add any missing required columns
    missing_cols = [col for col in ['Status', 'Last Updated By'] if col not in headers]
    if len(missing_cols) == 0:
        return
    for col_idx, col in enumerate(missing_cols, start=1 + len(headers)):
        worksheet.update_cell(1, col_idx, col)
        st.success(f"Added '{col}' column to the spreadsheet")
    st.cache_data.clear()  # Clear cache to reflect changes
    st.rerun()  # Rerun to reflect changes immediately


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_spreadsheet_data(spreadsheet_id, worksheet_name='Form Responses 1'):
    """
    Load data from a Google Spreadsheet, filtering out ignored/completed items

    Args:
        spreadsheet_id (str): The ID of the Google Spreadsheet
        worksheet_name (str): Name of the worksheet to load

    Returns:
        pandas.DataFrame: The spreadsheet data as a DataFrame
    """
    try:
        # Get the Google Sheets client
        client = get_google_sheets_client()

        # Open the spreadsheet by ID
        spreadsheet = client.open_by_key(spreadsheet_id)

        # Get the specified worksheet
        worksheet = spreadsheet.worksheet(worksheet_name)

        # Get all records as a list of dictionaries
        records = worksheet.get_all_records()

        # Convert to pandas DataFrame
        df = pd.DataFrame(records)

        if not df.empty:
            # Filter out ignored and completed submissions
            df = df[~df['Status'].isin(['Ignored', 'Added to Calendar'])]

            # Filter out columns that are not needed for display
            df = df.drop(columns=['Status', 'Last Updated By'], errors='ignore')

            # Reset index for display
            df = df.reset_index(drop=True)

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
    Get the list of authorized users from the spreadsheet

    Args:
        spreadsheet_id (str): The ID of the Google Spreadsheet

    Returns:
        set: List of authorized usernames
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
    spreadsheet_id, row_idx, status, username, worksheet_name='Form Responses 1'
):
    """
    Update the status of a submission in the spreadsheet

    Args:
        spreadsheet_id (str): The ID of the Google Spreadsheet
        row_idx (int): Row index in the original sheet (1-indexed, accounting for header)
        status (str): New status to set
        username (str): Username of the person making the change
        worksheet_name (str): Name of the worksheet

    Returns:
        bool: Success status
    """
    try:
        client = get_google_sheets_client()
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)

        # Get headers to find Status column
        headers = worksheet.row_values(1)

        if 'Status' in headers:
            status_col = headers.index('Status') + 1
        else:
            st.error('Status column not found')
            return False

        if 'Last Updated By' in headers:
            last_updated_col = headers.index('Last Updated By') + 1
        else:
            st.error('Last Updated By column not found')
            return False

        # Update status
        worksheet.update_cell(
            row_idx + 2, status_col, status
        )  # +2: +1 for header row, +1 for 1-based indexing

        # Update last updated by
        worksheet.update_cell(row_idx + 2, last_updated_col, username)

        # Clear cache to reflect changes
        st.cache_data.clear()

        return True

    except Exception as e:
        st.error('Error updating submission status:')
        st.exception(e)
        return False


def get_original_row_index(spreadsheet_id, selected_row_data, worksheet_name='Form Responses 1'):
    """
    Find the original row index in the spreadsheet for a selected row from filtered data

    Args:
        spreadsheet_id (str): The ID of the Google Spreadsheet
        selected_row_data (dict): The selected row data
        worksheet_name (str): Name of the worksheet

    Returns:
        int: Original row index (0-indexed, not including header)
    """
    try:
        client = get_google_sheets_client()
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)

        # Get all records
        all_records = worksheet.get_all_records()

        # Find matching row - compare key fields
        for idx, record in enumerate(all_records):
            # Use Summary and Event Date as unique identifiers
            if record.get('Summary') == selected_row_data.get('Summary') and record.get(
                'Event Date'
            ) == selected_row_data.get('Event Date'):
                return idx

        return None

    except Exception as e:
        st.error('Error finding original row:')
        st.exception(e)
        return None


@st.cache_resource
def get_google_calendar_service():
    """
    Create and cache a Google Calendar service using service account credentials
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


def add_event_to_calendar(summary, description, start, end):
    """
    Add an event to the Google Calendar using the provided event data.
    Args:
        event_data (dict): Dictionary containing event details
    Returns:
        bool: Success status
    """
    if (calendar_id := st.secrets.get('calendar_id')) is None:
        st.error('Calendar ID not found in secrets. Please add it to .streamlit/secrets.toml')
        return False
    try:
        service = get_google_calendar_service()
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start,
                'timeZone': 'america/chicago',
            },
            'end': {
                'dateTime': end,
                'timeZone': 'america/chicago',
            },
            # Add other fields as needed
        }
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


# Main application
def main():
    st.title('Form Submission Review')

    if not st.user.is_logged_in:
        if st.button('Log in'):
            st.login()
        st.stop()
    else:
        st.write(f'Hello, {st.user.name}!')

    # Get spreadsheet ID from secrets
    if (spreadsheet_id := st.secrets.get('spreadsheet_id')) is None:
        st.error('`spreadsheet_id` not found in secrets. Please add it to .streamlit/secrets.toml')
        st.stop()

    # Add link to sheet and refresh button at the top
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        sheet_url = f'https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit'
        st.link_button('Form Responses GSheet', url=sheet_url, icon=':material/open_in_new:')

    with col2:
        if st.button('🔄 Refresh Data', help='Re-load the data from the GSheet.'):
            st.cache_data.clear()
            st.rerun()
    with col3:
        if st.button('Log out'):
            st.logout()

    if st.user.email not in get_authorized_users(spreadsheet_id):
        st.error(
            f'Your email ({st.user.email}) is not in the list of authorized users. '
            'Please check the Authorized Users sheet in the form responses spreadsheet.'
        )
        st.stop()

    st.divider()

    # Ensure Status column exists
    ensure_status_columns(spreadsheet_id)

    # Load and display submissions
    st.header('Pending Submissions')

    with st.spinner('Loading submissions...'):
        df = load_spreadsheet_data(spreadsheet_id)

    if df.empty:
        st.info('No pending submissions to review.')
        return

    st.success(f'Loaded {len(df)} pending submissions')

    # Create a display dataframe (exclude Status from display, rename Timestamp)
    display_df = df.copy()

    # Rename Timestamp column to Submission Time for display
    if 'Timestamp' in display_df.columns:
        display_df = display_df.rename(columns={'Timestamp': 'Submission Time'})

    # Display the dataframe with row selection
    selected_indices = st.dataframe(
        display_df,
        use_container_width=True,
        on_select='rerun',
        selection_mode='single-row',
        hide_index=True,
    )

    # Handle row selection
    if selected_indices['selection']['rows']:  # type: ignore
        selected_row_idx = selected_indices['selection']['rows'][0]  # type: ignore
        selected_row_data = df.iloc[selected_row_idx].to_dict()

        st.divider()
        st.subheader('Edit Submission Details')

        # Create editable fields for the selected submission
        edited_data = {}

        # Remove fields that shouldn't be edited
        fields_to_exclude = ['Status', 'Timestamp']
        fields_to_edit = [
            field for field in selected_row_data.keys() if field not in fields_to_exclude
        ]

        for idx, field in enumerate(fields_to_edit):
            value = selected_row_data.get(field, '')
            if field == 'Event Date':
                # Convert string to date for st.date_input
                try:
                    date_value = datetime.strptime(str(value), '%m/%d/%Y').date()
                except Exception:
                    date_value = datetime.today().date()
                edited_data[field] = st.date_input(field, value=date_value, key=f'edit_{field}')
            elif field == 'Description':
                # Use a text area for longer descriptions
                edited_data[field] = st.text_area(
                    field, value=str(value) if value else '', key=f'edit_{field}'
                )
            else:
                edited_data[field] = st.text_input(
                    field, value=str(value) if value else '', key=f'edit_{field}'
                )

        # Highlight the key fields
        if 'Summary' in edited_data and 'Event Date' in edited_data:
            st.info(f'**Event:** {edited_data["Summary"]} on {edited_data["Event Date"]}')

        # Action buttons
        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            if st.button('🚫 Mark as Ignored', type='secondary'):
                # Find original row index
                original_row_idx = get_original_row_index(spreadsheet_id, selected_row_data)
                if original_row_idx is not None:
                    success = update_submission_status(
                        spreadsheet_id,
                        original_row_idx,
                        'Ignored',
                        st.user.name,
                    )
                    if success:
                        st.success('Submission marked as ignored!')
                        st.rerun()
                else:
                    st.error('Could not find original row to update')

        with col2:
            if st.button('📅 Add to Calendar', type='primary'):
                original_row_idx = get_original_row_index(spreadsheet_id, selected_row_data)
                if original_row_idx is not None:
                    event_data = edited_data.copy()
                    event_date = event_data['Event Date'].strftime('%-m/%-d/%Y')
                    start_time = event_data.get('Start Time', '09:00')
                    end_time = event_data.get('End Time', '10:00')
                    # Combine date and time, convert to RFC3339
                    start_dt = pd.to_datetime(f'{event_date} {start_time}')
                    end_dt = pd.to_datetime(f'{event_date} {end_time}')
                    calendar_success = add_event_to_calendar(
                        summary=event_data.get('Summary', 'No Title'),
                        description=event_data.get('Description', ''),
                        start=start_dt.isoformat(),
                        end=end_dt.isoformat(),
                    )
                    if calendar_success:
                        success = update_submission_status(
                            spreadsheet_id,
                            original_row_idx,
                            'Added to Calendar',
                            'current_user',
                        )
                        if success:
                            st.success(
                                f"Event '{edited_data.get('Summary', 'Unknown')}' added to calendar and marked as added!"
                            )
                            st.rerun()
                    else:
                        st.error('Failed to add event to calendar.')
                else:
                    st.error('Could not find original row to update')

        with col3:
            if st.button('🔄 Refresh Data', key='bottom_refresh'):
                st.cache_data.clear()
                st.rerun()

    else:
        st.info(
            'Select a row from the table above to review and edit the submission.',
            icon=':material/arrow_upward:',
        )


if __name__ == '__main__':
    main()
