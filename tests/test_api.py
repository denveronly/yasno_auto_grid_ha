from datetime import datetime

from custom_components.yasno.api import KYIV, outages

DAY = {
    "today": {"date": "2026-10-27T00:00:00+02:00", "status": "ScheduleApplies", "slots": [
        {"start": 0, "end": 240, "type": "NotPlanned"},
        {"start": 240, "end": 480, "type": "Definite"},
        {"start": 1260, "end": 1440, "type": "Definite"},
    ]},
    "tomorrow": {"date": "2026-10-28T00:00:00+02:00", "status": "ScheduleApplies", "slots": [
        {"start": 0, "end": 120, "type": "Definite"},
        {"start": 600, "end": 840, "type": "Definite"},
    ]},
    "updatedOn": "2026-10-27T10:00:00+00:00",
}


def test_outages_merge_over_midnight():
    result = outages(DAY, datetime(2026, 10, 27, 12, 0, tzinfo=KYIV))
    assert [(o.start.isoformat(), o.end.isoformat()) for o in result] == [
        ("2026-10-27T04:00:00+02:00", "2026-10-27T08:00:00+02:00"),
        ("2026-10-27T21:00:00+02:00", "2026-10-28T02:00:00+02:00"),
        ("2026-10-28T10:00:00+02:00", "2026-10-28T14:00:00+02:00"),
    ]
    assert result[1].minutes == 300


def test_waiting_and_emergency_days_have_no_slots():
    data = {
        "today": {**DAY["today"], "status": "EmergencyShutdowns"},
        "tomorrow": {**DAY["tomorrow"], "status": "WaitingForSchedule"},
    }
    assert outages(data, datetime(2026, 10, 27, 12, 0, tzinfo=KYIV)) == []


def test_dst_day_keeps_wall_clock():
    data = {"today": {"date": "2026-10-25T00:00:00+03:00", "status": "ScheduleApplies",
                      "slots": [{"start": 600, "end": 720, "type": "Definite"}]}}
    (o,) = outages(data, datetime(2026, 10, 25, 1, 0, tzinfo=KYIV))
    assert (o.start.hour, o.end.hour, o.start.utcoffset().total_seconds()) == (10, 12, 7200)


def test_probable_week_over_days():
    from custom_components.yasno.api import probable_group, probable_outages

    week = {"0": [{"start": 0, "end": 60, "type": "Definite"}], "6": [{"start": 1380, "end": 1440, "type": "Definite"}]}
    data = probable_group({"25": {"dsos": {"902": {"groups": {"1.2": {"slots": week}}}}}}, 25, 902, "1.2")
    # Tuesday: the next Sunday 23:00 and Monday 00:00 merge into one outage.
    result = outages_ = probable_outages(data, datetime(2026, 10, 27, 12, 0, tzinfo=KYIV))
    assert [(o.start.isoformat(), o.end.isoformat()) for o in outages_] == [
        ("2026-11-01T23:00:00+02:00", "2026-11-02T01:00:00+02:00"),
    ]
    assert result[0].minutes == 120
    assert probable_group({}, 25, 902, "1.2") == {}
