from datetime import date

import pytest

from main import monthly_byday


@pytest.mark.parametrize(
    'd',
    [
        date(2025, 8, 23),  # 4th Saturday -> 4SA
        date(2025, 1, 6),  # 1st Monday  -> 1MO
        date(2025, 3, 18),  # 3rd Tuesday -> 3TU (verify mapping)
        date(2025, 11, 30),  # 5th Sunday  -> 5SU (some months have 5 occurrences)
    ],
)
def test_monthly_byday_matches_expected_formula(d):
    """monthly_byday should follow the formula: ordinal = ((day-1)//7)+1 and weekday mapping."""
    expected_ordinal = ((d.day - 1) // 7) + 1
    weekday_map = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
    expected = f'BYDAY={expected_ordinal}{weekday_map[d.weekday()]};'
    assert monthly_byday(d) == expected
