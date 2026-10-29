<p align="center"><img src="custom_components/yasno/brand/logo@2x.png" alt="Outage schedule" width="380"></p>

# Yasno / DTEK outages for Home Assistant

[Українська](README.md) · [Русский](README.ru.md) · **English**

Planned power outage schedule for your address or group:

- **Kyiv, Dnipro** – from [Yasno](https://yasno.ua); the outage group is found by **street
  and house number**.
- **Kyiv region** – the DTEK KREM schedule ([dtek-krem.com.ua](https://www.dtek-krem.com.ua/ua/shutdowns)),
  read from the [outage-data-ua](https://github.com/Baskerville42/outage-data-ua) mirror,
  which loads the DTEK site with a headless browser every few minutes (the site itself
  blocks scripts). You choose your group (черга); find it once by address on the DTEK site.

The old `api.yasno.com.ua/api/v1/pages/home/schedule-turn-off-electricity` no longer
exists; this integration uses the current `app.yasno.ua` blackout-service API.

## Install (HACS)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/denveronly/yasno_auto_grid_ha`,
   category **Integration**.
2. Install **Yasno / DTEK outages** and restart Home Assistant.
3. **Settings → Devices & services → Add integration → Yasno / DTEK outages**.

Manual install: copy `custom_components/yasno` to `/config/custom_components/` and restart.

## Setup

First choose the source: **Kyiv, Dnipro (Yasno)** or **Kyiv region (DTEK)**. For DTEK, pick
your group and you are done (entities are `…dtek_kiivska_oblast_2_2_…`). For Yasno:

1. **Region** (Київ, Дніпро, …) and the distribution company (asked only when there are several).
2. **By address**: type part of the street name (`хрещ`), pick the street, type the house
   number (`22`, `22/1`). Yasno returns the group (e.g. `3.1`).
   **Choose the group**: pick it from the list instead.

The address is looked up again once a day: when Yasno moves the house to another group,
the integration follows (and logs it).

## Entities

| Entity | State |
|---|---|
| `binary_sensor.yasno_…_grid_status` | **on** while there is power by the schedule, **off** during a scheduled outage |
| `sensor.yasno_…_minutes_to_outage` | minutes until the next outage starts; `9999` when none is scheduled |
| `sensor.yasno_…_minutes_to_power_on` | during an outage: minutes until power comes back; `0` while there is power |
| `sensor.yasno_…_outage_duration` | length of the next outage, minutes (adjacent slots and over-midnight outages are merged) |
| `sensor.yasno_…_next_outage` | start of the next outage (timestamp) |
| `sensor.yasno_…_power_back` | end of the outage in effect, or of the next one (timestamp) |
| `sensor.yasno_…_outage_hours_today` / `_tomorrow` | hours without power by the schedule; unknown until the day's schedule is published |
| `sensor.yasno_…_outages_today` / `_tomorrow` | number of outages that day |
| `binary_sensor.yasno_…_emergency_outages` | on while Yasno reports emergency outages (the schedule does not apply) |
| `binary_sensor.yasno_…_tomorrow_schedule_published` | on once tomorrow's schedule is out |
| `binary_sensor.yasno_…_schedule` / `_tomorrow` | **on** when outages go by the schedule that day, **off** with no outages, while waiting for the schedule or under emergency outages; Yasno's status (`ScheduleApplies`, `NoOutages`, `WaitingForSchedule`, `EmergencyShutdowns`) and the raw slots are attributes |
| `sensor.yasno_…_schedule_updated` | when Yasno last changed the schedule (diagnostic) |
| `sensor.yasno_…_minutes_to_probable_outage` | minutes to the next outage of the weekly **probable** schedule ("можливі відключення"); `9999` when none |
| `sensor.yasno_…_next_probable_outage` | its start (timestamp); the next 8 days in the `outages` attribute |
| `binary_sensor.yasno_…_probable_outage_now` | on during a probable outage |
| `sensor.yasno_…_group` | group, e.g. `3.1` |
| `calendar.yasno_…_outages` | planned outages, and probable ones on days without a published schedule |

The planned schedule is read every 10 minutes, the probable one every hour; the entities are
recalculated every minute. Days that are waiting for a schedule or under emergency outages
have no planned outages – the probable schedule is what to expect then.

With DTEK, the probable schedule is DTEK's weekly "possible outages" (можливо відключення),
and there is no emergency-outage flag (that entity stays off). Add the integration once per
address or group to follow several.

### With BatteryAI

In the [BatteryAI](https://github.com/denveronly/batteryai) add-on, Settings → Sensors:

- *Minutes to outage* → `sensor.yasno_…_minutes_to_outage`
- *Outage duration* → `sensor.yasno_…_outage_duration`
- *Emergency outages* → `binary_sensor.yasno_…_emergency_outages`

Before tomorrow's schedule is published, `minutes_to_probable_outage` can stand in for
*Minutes to outage*.

## Development

```sh
pip install pytest-homeassistant-custom-component
pytest -q
```
