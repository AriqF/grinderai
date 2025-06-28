from datetime import datetime
import pytz


def get_current_time(loc: str):
    jakarta_tz = pytz.timezone(loc)
    curr_time = datetime.now(jakarta_tz)
    return curr_time
