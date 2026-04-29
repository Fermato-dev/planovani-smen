"""Czech public holidays calculator — no external dependencies."""
from datetime import date, timedelta


def _easter_sunday(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_czech_holidays(year: int) -> dict:
    """Return {date: name} for all Czech public holidays in given year."""
    h = {}

    # Fixed-date holidays
    fixed = [
        (1,  1,  'Nový rok'),
        (1,  5,  'Svátek práce'),
        (8,  5,  'Den vítězství'),
        (5,  7,  'Den Cyrila a Metoděje'),
        (6,  7,  'Den Jana Husa'),
        (28, 9,  'Den české státnosti'),
        (28, 10, 'Den vzniku Československa'),
        (17, 11, 'Den boje za svobodu a demokracii'),
        (24, 12, 'Štědrý den'),
        (25, 12, '1. svátek vánoční'),
        (26, 12, '2. svátek vánoční'),
    ]
    for day, month, name in fixed:
        h[date(year, month, day)] = name

    # Movable: Easter Monday (Velikonoční pondělí)
    h[_easter_sunday(year) + timedelta(days=1)] = 'Velikonoční pondělí'

    return h


def get_holidays_for_dates(dates: list) -> dict:
    """Return {date_str: holiday_name} for a list of date objects."""
    years = {d.year for d in dates}
    all_holidays = {}
    for y in years:
        all_holidays.update(get_czech_holidays(y))
    return {d.isoformat(): all_holidays[d] for d in dates if d in all_holidays}
