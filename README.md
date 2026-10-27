# Yasno outages for Home Assistant

Planned power outage schedule from [Yasno](https://yasno.ua) (DTEK Kyiv / Dnipro) for your
address. The outage group is found by **street and house number** – no need to know it.

The old `api.yasno.com.ua/api/v1/pages/home/schedule-turn-off-electricity` no longer
exists; this integration uses the current `app.yasno.ua` blackout-service API.

## Install (HACS)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/denveronly/yasno_auto_grid_ha`,
   category **Integration**.
2. Install **Yasno outages** and restart Home Assistant.
3. **Settings → Devices & services → Add integration → Yasno outages**.

Manual install: copy `custom_components/yasno` to `/config/custom_components/` and restart.

## Setup

1. **Region** (Київ, Дніпро, …) and the distribution company (asked only when there are several).
2. **By address**: type part of the street name (`хрещ`), pick the street, type the house
   number (`22`, `22/1`). Yasno returns the group (e.g. `3.1`).
   **Choose the group**: pick it from the list instead.

The address is looked up again once a day: when Yasno moves the house to another group,
the integration follows (and logs it).

## Entities

| Entity | State |
|---|---|
| `sensor.yasno_…_group` | group, e.g. `3.1` |
| `sensor.yasno_…_minutes_to_outage` | minutes until the next outage starts; `9999` when none is scheduled |
| `sensor.yasno_…_outage_duration` | length of the next outage, minutes (adjacent slots and over-midnight outages are merged) |
| `sensor.yasno_…_next_outage` | start of the next outage (timestamp) |
| `sensor.yasno_…_power_back` | end of the outage in effect, or of the next one (timestamp) |
| `sensor.yasno_…_schedule_status` | today's status: `ScheduleApplies`, `WaitingForSchedule`, `EmergencyShutdowns`, `NoOutages`; attributes: raw slots for today / tomorrow, merged `outages`, `status_tomorrow`, `updated_on` |
| `binary_sensor.yasno_…_outage_now` | on during a scheduled outage |
| `binary_sensor.yasno_…_emergency_outages` | on while Yasno reports emergency outages (the schedule does not apply) |

Yasno is read every 10 minutes; the entities are recalculated every minute. Days that are
waiting for a schedule or under emergency outages have no planned outages.

### With BatteryAI

In the [BatteryAI](https://github.com/denveronly/batteryai) add-on, Settings → Sensors:

- *Minutes to outage* → `sensor.yasno_…_minutes_to_outage`
- *Outage duration* → `sensor.yasno_…_outage_duration`
- *Emergency outages* → `binary_sensor.yasno_…_emergency_outages`

## Development

```sh
pip install pytest-homeassistant-custom-component
pytest -q
```
