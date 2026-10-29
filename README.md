<p align="center"><img src="custom_components/yasno/brand/logo@2x.png" alt="Графік відключень" width="380"></p>

# Графік відключень Ясно / ДТЕК для Home Assistant

**Українська** · [Русский](README.ru.md) · [English](README.en.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Validate](https://github.com/denveronly/yasno_auto_grid_ha/actions/workflows/validate.yml/badge.svg)](https://github.com/denveronly/yasno_auto_grid_ha/actions/workflows/validate.yml)

Інтеграція показує в Home Assistant графік відключень світла для вашої адреси: чи є
зараз світло за графіком, скільки хвилин до відключення і до увімкнення, скільки годин
без світла сьогодні й завтра, можливі відключення на тиждень і календар.

| Де | Джерело | Як визначається черга |
|---|---|---|
| **Київ, Дніпро** | [Ясно](https://yasno.ua) | **автоматично за вулицею та номером будинку** |
| **Київська область** | ДТЕК КРЕМ ([dtek-krem.com.ua](https://www.dtek-krem.com.ua/ua/shutdowns)) | ви обираєте свою чергу зі списку |

Можна додати кілька адрес або черг — наприклад, квартиру в Києві та будинок в області.

## Встановлення

### Через HACS (рекомендовано)

1. HACS → ⋮ (праворуч угорі) → **Custom repositories**.
2. Repository: `https://github.com/denveronly/yasno_auto_grid_ha`, Type: **Integration** → **Add**.
3. Знайдіть **Yasno / DTEK outages** → **Download**.
4. Перезапустіть Home Assistant.

### Вручну

Скопіюйте папку `custom_components/yasno` у `/config/custom_components/` і перезапустіть
Home Assistant.

## Налаштування

**Налаштування → Пристрої та служби → Додати інтеграцію → Yasno / DTEK outages.**

Спочатку оберіть джерело:

### Київ, Дніпро (Ясно)

1. **Регіон** — Київ або Дніпро (оператор питається лише тоді, коли їх кілька).
2. **За адресою (вулиця і будинок)**:
   - введіть частину назви вулиці так, як на yasno.ua (`хрещ`, `Лесі`), і оберіть вулицю зі списку;
   - введіть номер будинку (`22`, `22/1`, `22-а`) — Ясно поверне вашу групу (наприклад `3.1`).

   Або **Обрати групу**, якщо ви її знаєте.

Раз на добу адреса перевіряється заново: якщо Ясно переведе будинок в іншу групу,
інтеграція перемкнеться сама (і напише про це в журнал).

### Київська область (ДТЕК)

Оберіть свою **чергу** (1.1 … 6.2). Дізнатися її можна один раз за адресою на
[dtek-krem.com.ua/ua/shutdowns](https://www.dtek-krem.com.ua/ua/shutdowns).

> Сайт ДТЕК блокує скрипти (захист від ботів), тому графік береться з відкритого
> дзеркала [outage-data-ua](https://github.com/Baskerville42/outage-data-ua), яке кожні
> кілька хвилин відкриває сайт ДТЕК у браузері й публікує ті самі дані. З тієї ж причини
> чергу для області неможливо визначити за адресою автоматично.

## Сутності

Назви сутностей починаються з назви пристрою: `…yasno_vul_khreshchatik_22_…` для адреси
в Ясно, `…dtek_kiivska_oblast_2_2_…` для черги ДТЕК. Точні ідентифікатори видно в
**Налаштування → Пристрої та служби → Сутності**.

### Головне

| Сутність | Значення |
|---|---|
| **Стан мережі** `binary_sensor.…_grid_status` | **on** — світло є за графіком, **off** — відключення |
| **Хвилин до відключення** `sensor.…_minutes_to_outage` | хвилин до початку наступного відключення; `9999`, якщо відключень не заплановано |
| **Хвилин до увімкнення** `sensor.…_minutes_to_power_on` | під час відключення — хвилин до появи світла; `0`, коли світло є |
| **Тривалість відключення** `sensor.…_outage_duration` | тривалість наступного відключення, хв |
| **Наступне відключення** `sensor.…_next_outage` | час початку наступного відключення |
| **Увімкнення** `sensor.…_power_back` | коли повернеться світло (кінець поточного або наступного відключення) |

Сусідні слоти й відключення через північ (23:00–24:00 + 00:00–02:00) об'єднуються в одне.

### Графік

| Сутність | Значення |
|---|---|
| **Графік** / **Графік на завтра** `binary_sensor.…_schedule` / `_schedule_tomorrow` | **on** — у цей день діють відключення за графіком; **off** — відключень немає, графік ще не опубліковано або діють аварійні відключення. Статус Ясно та слоти — в атрибутах |
| **Графік на завтра опубліковано** `binary_sensor.…_tomorrow_schedule_published` | **on**, щойно вийшов графік на завтра |
| **Годин без світла сьогодні / завтра** `sensor.…_outage_hours_today` / `_tomorrow` | сумарно годин відключень; невідомо, доки графік на день не опубліковано |
| **Відключень сьогодні / завтра** `sensor.…_outages_today` / `_tomorrow` | кількість відключень |
| **Аварійні відключення** `binary_sensor.…_emergency_outages` | **on**, коли Ясно повідомляє про аварійні відключення (графік не діє). У ДТЕК такої ознаки немає — завжди off |
| **Графік оновлено** `sensor.…_schedule_updated` | коли графік востаннє змінювався (діагностика) |
| **Група** `sensor.…_group` | ваша група / черга, наприклад `3.1` |

### Можливі відключення

Тижневий графік «можливих відключень» — корисний, доки точний графік на завтра ще не вийшов.

| Сутність | Значення |
|---|---|
| **Хвилин до можливого відключення** `sensor.…_minutes_to_probable_outage` | `9999`, якщо немає |
| **Наступне можливе відключення** `sensor.…_next_probable_outage` | час початку; найближчі 8 днів — в атрибуті `outages` |
| **Можливе відключення зараз** `binary_sensor.…_probable_outage_now` | **on** під час можливого відключення |

### Календар

`calendar.…_outages` — відключення за графіком, а на дні без опублікованого графіка —
можливі. Видно в розділі **Календар** і можна використовувати в автоматизаціях.

Графік зчитується кожні 10 хвилин (можливі відключення в Ясно — щогодини), значення
перераховуються щохвилини.

## Приклади

### Сповіщення за 30 хвилин до відключення

```yaml
automation:
  - alias: "Світло: за 30 хв відключення"
    trigger:
      - platform: numeric_state
        entity_id: sensor.yasno_vul_khreshchatik_22_minutes_to_outage
        below: 31
    action:
      - service: notify.mobile_app_phone
        data:
          message: >
            Через {{ states('sensor.yasno_vul_khreshchatik_22_minutes_to_outage') }} хв
            відключення на {{ states('sensor.yasno_vul_khreshchatik_22_outage_duration') }} хв.
```

### Світло повернулося / вийшов графік на завтра

```yaml
automation:
  - alias: "Світло: є за графіком"
    trigger:
      - platform: state
        entity_id: binary_sensor.yasno_vul_khreshchatik_22_grid_status
        to: "on"
    action:
      - service: notify.mobile_app_phone
        data:
          message: "За графіком світло вже є."

  - alias: "Світло: графік на завтра"
    trigger:
      - platform: state
        entity_id: binary_sensor.yasno_vul_khreshchatik_22_tomorrow_schedule_published
        to: "on"
    action:
      - service: notify.mobile_app_phone
        data:
          message: >
            Графік на завтра: {{ states('sensor.yasno_vul_khreshchatik_22_outage_hours_tomorrow') }} год
            без світла, відключень: {{ states('sensor.yasno_vul_khreshchatik_22_outages_tomorrow') }}.
```

### Картка на дашборд

```yaml
type: entities
title: Світло
entities:
  - entity: binary_sensor.yasno_vul_khreshchatik_22_grid_status
  - entity: sensor.yasno_vul_khreshchatik_22_minutes_to_outage
  - entity: sensor.yasno_vul_khreshchatik_22_minutes_to_power_on
  - entity: sensor.yasno_vul_khreshchatik_22_next_outage
    format: time
  - entity: sensor.yasno_vul_khreshchatik_22_outage_hours_today
  - entity: sensor.yasno_vul_khreshchatik_22_outage_hours_tomorrow
```

## Разом з BatteryAI

У додатку [BatteryAI](https://github.com/denveronly/batteryai) → Settings → Sensors:

- *Minutes to outage* → `sensor.…_minutes_to_outage`
- *Outage duration* → `sensor.…_outage_duration`
- *Emergency outages* → `binary_sensor.…_emergency_outages`

Поки графік на завтра не опубліковано, замість *Minutes to outage* можна вказати
`sensor.…_minutes_to_probable_outage`.

## Питання

**Вулицю не знайдено.** Вводьте частину назви без «вул.» і так, як вона написана на
yasno.ua (українською). Якщо адреси немає в Ясно — оберіть групу вручну.

**Сутності «недоступні».** Джерело не відповідає; інтеграція повторює запит кожні
10 хвилин і показує останній отриманий графік. Деталі — в журналі (`custom_components.yasno`).

**Старий `api.yasno.com.ua` не працює.** Його більше не існує; інтеграція використовує
поточне API `app.yasno.ua`.

## Розробка

```sh
pip install pytest-homeassistant-custom-component
pytest -q
```

Інтеграція неофіційна й не пов'язана з Ясно чи ДТЕК. Ліцензія MIT.
