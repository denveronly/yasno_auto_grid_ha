# Changelog

## 0.2.0

- **Grid status** (`binary_sensor.…_grid_status`) replaces *Outage now*: on while there is
  power by the schedule, off during an outage. The old entity is removed.
- **Minutes to power on**: during an outage, minutes until the power is back (0 with power).
- **Probable outages** from Yasno's weekly schedule: minutes to / next probable outage,
  probable outage now.
- **Schedule** / **Schedule tomorrow** (on / off) replace the *Schedule status* text sensor:
  on when outages go by the schedule, Yasno's status is an attribute. The old entity is removed.
- Hours without power and number of outages today / tomorrow; *Tomorrow schedule
  published*; *Schedule updated*.
- **Calendar** with planned outages, and probable ones on days without a schedule.
- *Emergency outages* shows On / Off instead of OK / Problem.

## 0.1.0

- First version: group by street and house number, minutes to outage, outage duration,
  next outage, power back, schedule status, outage now, emergency outages.
