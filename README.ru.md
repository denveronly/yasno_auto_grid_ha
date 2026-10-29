<p align="center"><img src="custom_components/yasno/brand/logo@2x.png" alt="График отключений" width="380"></p>

# График отключений Ясно / ДТЕК для Home Assistant

[Українська](README.md) · **Русский** · [English](README.en.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Validate](https://github.com/denveronly/yasno_auto_grid_ha/actions/workflows/validate.yml/badge.svg)](https://github.com/denveronly/yasno_auto_grid_ha/actions/workflows/validate.yml)

Интеграция показывает в Home Assistant график отключений света для вашего адреса: есть ли
сейчас свет по графику, сколько минут до отключения и до включения, сколько часов без
света сегодня и завтра, возможные отключения на неделю и календарь.

| Где | Источник | Как определяется группа |
|---|---|---|
| **Киев, Днепр** | [Ясно](https://yasno.ua) | **автоматически по улице и номеру дома** |
| **Киевская область** | ДТЕК КРЕМ ([dtek-krem.com.ua](https://www.dtek-krem.com.ua/ua/shutdowns)) | вы выбираете свою очередь из списка |

Можно добавить несколько адресов или очередей — например, квартиру в Киеве и дом в области.

## Установка

### Через HACS (рекомендуется)

1. HACS → ⋮ (справа вверху) → **Custom repositories**.
2. Repository: `https://github.com/denveronly/yasno_auto_grid_ha`, Type: **Integration** → **Add**.
3. Найдите **Yasno / DTEK outages** → **Download**.
4. Перезапустите Home Assistant.

### Вручную

Скопируйте папку `custom_components/yasno` в `/config/custom_components/` и перезапустите
Home Assistant.

## Настройка

**Настройки → Устройства и службы → Добавить интеграцию → Yasno / DTEK outages.**

Сначала выберите источник:

### Киев, Днепр (Ясно)

1. **Регион** — Киев или Днепр (оператор спрашивается, только если их несколько).
2. **По адресу (улица и дом)**:
   - введите часть названия улицы так, как на yasno.ua (`хрещ`, `Лесі`), и выберите улицу из списка;
   - введите номер дома (`22`, `22/1`, `22-а`) — Ясно вернёт вашу группу (например `3.1`).

   Или **Выбрать группу**, если вы её знаете.

Раз в сутки адрес проверяется заново: если Ясно переведёт дом в другую группу,
интеграция переключится сама (и напишет об этом в журнал).

### Киевская область (ДТЕК)

Выберите свою **очередь** (1.1 … 6.2). Узнать её можно один раз по адресу на
[dtek-krem.com.ua/ua/shutdowns](https://www.dtek-krem.com.ua/ua/shutdowns).

> Сайт ДТЕК блокирует скрипты (защита от ботов), поэтому график берётся из открытого
> зеркала [outage-data-ua](https://github.com/Baskerville42/outage-data-ua), которое каждые
> несколько минут открывает сайт ДТЕК в браузере и публикует те же данные. По той же
> причине очередь для области нельзя определить по адресу автоматически.

## Сущности

Имена сущностей начинаются с имени устройства: `…yasno_vul_khreshchatik_22_…` для адреса
в Ясно, `…dtek_kiivska_oblast_2_2_…` для очереди ДТЕК. Точные идентификаторы видны в
**Настройки → Устройства и службы → Сущности**.

### Главное

| Сущность | Значение |
|---|---|
| **Состояние сети** `binary_sensor.…_grid_status` | **on** — свет есть по графику, **off** — отключение |
| **Минут до отключения** `sensor.…_minutes_to_outage` | минут до начала следующего отключения; `9999`, если отключений не запланировано |
| **Минут до включения** `sensor.…_minutes_to_power_on` | во время отключения — минут до появления света; `0`, когда свет есть |
| **Длительность отключения** `sensor.…_outage_duration` | длительность следующего отключения, мин |
| **Следующее отключение** `sensor.…_next_outage` | время начала следующего отключения |
| **Включение** `sensor.…_power_back` | когда вернётся свет (конец текущего или следующего отключения) |

Соседние слоты и отключения через полночь (23:00–24:00 + 00:00–02:00) объединяются в одно.

### График

| Сущность | Значение |
|---|---|
| **График** / **График на завтра** `binary_sensor.…_schedule` / `_schedule_tomorrow` | **on** — в этот день действуют отключения по графику; **off** — отключений нет, график ещё не опубликован или идут аварийные отключения. Статус Ясно и слоты — в атрибутах |
| **График на завтра опубликован** `binary_sensor.…_tomorrow_schedule_published` | **on**, как только вышел график на завтра |
| **Часов без света сегодня / завтра** `sensor.…_outage_hours_today` / `_tomorrow` | всего часов отключений; неизвестно, пока график на день не опубликован |
| **Отключений сегодня / завтра** `sensor.…_outages_today` / `_tomorrow` | количество отключений |
| **Аварийные отключения** `binary_sensor.…_emergency_outages` | **on**, когда Ясно сообщает об аварийных отключениях (график не действует). У ДТЕК такого признака нет — всегда off |
| **График обновлён** `sensor.…_schedule_updated` | когда график последний раз менялся (диагностика) |
| **Группа** `sensor.…_group` | ваша группа / очередь, например `3.1` |

### Возможные отключения

Недельный график «возможных отключений» — полезен, пока точный график на завтра ещё не вышел.

| Сущность | Значение |
|---|---|
| **Минут до возможного отключения** `sensor.…_minutes_to_probable_outage` | `9999`, если нет |
| **Следующее возможное отключение** `sensor.…_next_probable_outage` | время начала; ближайшие 8 дней — в атрибуте `outages` |
| **Возможное отключение сейчас** `binary_sensor.…_probable_outage_now` | **on** во время возможного отключения |

### Календарь

`calendar.…_outages` — отключения по графику, а в дни без опубликованного графика —
возможные. Видно в разделе **Календарь** и можно использовать в автоматизациях.

График читается каждые 10 минут (возможные отключения в Ясно — каждый час), значения
пересчитываются каждую минуту.

## Примеры

### Уведомление за 30 минут до отключения

```yaml
automation:
  - alias: "Свет: за 30 мин отключение"
    trigger:
      - platform: numeric_state
        entity_id: sensor.yasno_vul_khreshchatik_22_minutes_to_outage
        below: 31
    action:
      - service: notify.mobile_app_phone
        data:
          message: >
            Через {{ states('sensor.yasno_vul_khreshchatik_22_minutes_to_outage') }} мин
            отключение на {{ states('sensor.yasno_vul_khreshchatik_22_outage_duration') }} мин.
```

### Свет вернулся / вышел график на завтра

```yaml
automation:
  - alias: "Свет: есть по графику"
    trigger:
      - platform: state
        entity_id: binary_sensor.yasno_vul_khreshchatik_22_grid_status
        to: "on"
    action:
      - service: notify.mobile_app_phone
        data:
          message: "По графику свет уже есть."

  - alias: "Свет: график на завтра"
    trigger:
      - platform: state
        entity_id: binary_sensor.yasno_vul_khreshchatik_22_tomorrow_schedule_published
        to: "on"
    action:
      - service: notify.mobile_app_phone
        data:
          message: >
            График на завтра: {{ states('sensor.yasno_vul_khreshchatik_22_outage_hours_tomorrow') }} ч
            без света, отключений: {{ states('sensor.yasno_vul_khreshchatik_22_outages_tomorrow') }}.
```

### Карточка на дашборд

```yaml
type: entities
title: Свет
entities:
  - entity: binary_sensor.yasno_vul_khreshchatik_22_grid_status
  - entity: sensor.yasno_vul_khreshchatik_22_minutes_to_outage
  - entity: sensor.yasno_vul_khreshchatik_22_minutes_to_power_on
  - entity: sensor.yasno_vul_khreshchatik_22_next_outage
    format: time
  - entity: sensor.yasno_vul_khreshchatik_22_outage_hours_today
  - entity: sensor.yasno_vul_khreshchatik_22_outage_hours_tomorrow
```

## Вместе с BatteryAI

В аддоне [BatteryAI](https://github.com/denveronly/batteryai) → Settings → Sensors:

- *Minutes to outage* → `sensor.…_minutes_to_outage`
- *Outage duration* → `sensor.…_outage_duration`
- *Emergency outages* → `binary_sensor.…_emergency_outages`

Пока график на завтра не опубликован, вместо *Minutes to outage* можно указать
`sensor.…_minutes_to_probable_outage`.

## Вопросы

**Улица не находится.** Вводите часть названия без «вул.» и так, как она написана на
yasno.ua (по-украински). Если адреса нет в Ясно — выберите группу вручную.

**Сущности «недоступны».** Источник не отвечает; интеграция повторяет запрос каждые
10 минут и показывает последний полученный график. Подробности — в журнале (`custom_components.yasno`).

**Старый `api.yasno.com.ua` не работает.** Его больше не существует; интеграция использует
текущее API `app.yasno.ua`.

## Разработка

```sh
pip install pytest-homeassistant-custom-component
pytest -q
```

Интеграция неофициальная и не связана с Ясно или ДТЕК. Лицензия MIT.
