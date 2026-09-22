# Ukraine - Education ЄДЕБО XML Import

[![License: LGPL-3](https://img.shields.io/badge/license-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0-standalone.html)

Плагін до `l10n_ua_education_edebo`. Додає підтримку XML-формату обміну
з Єдиною державною електронною базою освіти (МОН).

## Можливості

- Override `_parse_custom()` для `file_format='custom'`
- Гнучкий парсер з підтримкою кількох синонімів тегів (`<student>` / `<person>` /
  `<osoba>`, `<last_name>` / `<surname>` / `<prizvyshche>` тощо)
- Толерантний до XML-namespace
- Точка розширення `_edebo_xml_extract_persons(root)` для специфічного
  формату МОН (підключається дочірнім модулем)

## Приклад XML

```xml
<edebo>
  <students>
    <student>
      <last_name>Прізвище</last_name>
      <first_name>Імʼя</first_name>
      <middle_name>По-батькові</middle_name>
      <birthdate>2005-03-15</birthdate>
      <rnokpp>1234567890</rnokpp>
      <student_number>EDB-001</student_number>
      <member_type>student</member_type>
    </student>
  </students>
</edebo>
```

## Обмеження

- Експорт у XML ще НЕ реалізовано — потребує цифрового підпису і
  специфікації МОН (окремий PR за наявності контракту з регулятором)
- Реальна XSD-схема ЄДЕБО закрита і змінюється. За відсутності
  актуальної схеми — best-effort парсинг
