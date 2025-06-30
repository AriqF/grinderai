from datetime import datetime
import pytz


def get_current_time(loc: str):
    jakarta_tz = pytz.timezone(loc)
    curr_time = datetime.now(jakarta_tz)
    return curr_time


def get_mood_labels():
    return [
        "happy",
        "calm",
        "excited",
        "hopeful",
        "motivated",
        "grateful",
        "content",
        "neutral",
        "mixed",
        "sad",
        "tired",
        "exhausted",
        "overwhelmed",
        "stressed",
        "anxious",
        "frustrated",
        "burned out",
        "angry",
        "lonely",
        "discouraged",
        "guilty",
        "unmotivated",
        "insecure",
        "confused",
    ]
