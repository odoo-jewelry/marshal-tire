# l10n_ua_tax_cabinet

Модуль інтеграції з електронним кабінетом платника податків (cabinet.tax.gov.ua).

## Вимоги

Для роботи з КЕП (кваліфікованим електронним підписом) необхідно встановити бібліотеку **IIT EUSignCP** від Інституту Інформаційних Технологій.

## Встановлення бібліотеки IIT EUSignCP

### 1. Завантаження бібліотеки

Завантажте бібліотеку з офіційного сайту IIT:
- **Сайт:** https://iit.com.ua/downloads
- **Пряме посилання:** https://iit.com.ua/download/productfiles/EUSignCP-Linux-20241205.zip

```bash
# Створюємо директорію для бібліотеки
sudo mkdir -p /opt/iit/eu/sw

# Завантажуємо та розпаковуємо
cd /tmp
wget https://iit.com.ua/download/productfiles/EUSignCP-Linux-20241205.zip
unzip EUSignCP-Linux-20241205.zip

# Копіюємо файли бібліотеки (для x64)
sudo cp -r EUSignCP-Linux/sw/x64/* /opt/iit/eu/sw/

# Встановлюємо права
sudo chmod -R 755 /opt/iit/eu/sw
```

### 2. Встановлення залежностей

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y libssl-dev libcurl4-openssl-dev

# Fedora/RHEL/CentOS
sudo dnf install openssl-devel libcurl-devel
```

### 3. Налаштування шляху до бібліотеки

```bash
# Додаємо шлях до бібліотеки
echo "/opt/iit/eu/sw" | sudo tee /etc/ld.so.conf.d/iit.conf
sudo ldconfig
```

### 4. Завантаження сертифікатів АЦСК

Для роботи КЕП необхідні кореневі сертифікати акредитованих центрів сертифікації ключів (АЦСК).

```bash
# Створюємо директорію для сертифікатів
sudo mkdir -p /opt/iit/certificates

# Завантажуємо сертифікати АЦСК
cd /opt/iit/certificates

# Сертифікати ІДД ДПС України (обов'язково для cabinet.tax.gov.ua)
wget https://acskidd.gov.ua/download/CACertificates.p7b

# Або завантажте повний пакет CA сертифікатів з:
# https://iit.com.ua/download/productfiles/CAs.zip
```

### 5. Налаштування змінних середовища

Додайте в конфігурацію Odoo або системні змінні середовища:

```bash
# В /etc/environment або ~/.bashrc
export IIT_LIB_PATH=/opt/iit/eu/sw
export IIT_CERT_PATH=/opt/iit/certificates
```

Або в конфігурації Odoo (`odoo.conf`):

```ini
[options]
; ... інші налаштування ...

; IIT Library paths (можна задати через environment)
; Якщо не задано, використовуються значення за замовчуванням:
; IIT_LIB_PATH=/opt/iit/eu/sw
; IIT_CERT_PATH=/opt/iit/certificates
```

## Структура директорій

```
/opt/iit/
├── eu/
│   └── sw/                      # Бібліотека EUSignCP
│       ├── euscp.so             # Основна бібліотека (обов'язково!)
│       ├── libcrypto.so.1.1
│       ├── libssl.so.1.1
│       └── ...
└── certificates/                # Сертифікати
    ├── CACertificates.p7b       # Кореневі сертифікати АЦСК
    ├── *.cer                    # Додаткові сертифікати (опціонально)
    └── your_key.dat             # Ваш приватний ключ КЕП
```

## Підготовка ключа КЕП

### Підтримувані формати ключів

- `.dat` - файловий ключ ІІТ
- `.jks` - Java KeyStore
- `.pfx` / `.p12` - PKCS#12
- `.zs2` - захищене сховище ключів ІІТ

### Отримання ключа

1. **Від АЦСК ІДД ДПС:** https://acskidd.gov.ua/
2. **Від приватних АЦСК:** ПриватБанк, Вчасно, СОТА та інші
3. **Diia.Sign:** Експорт ключа з застосунку Дія

### Розміщення ключа

```bash
# Копіюємо ключ в директорію сертифікатів
cp /path/to/your_key.dat /opt/iit/certificates/

# Або вказуємо повний шлях при налаштуванні в Odoo
```

## Налаштування в Odoo

1. **Налаштування → Компанії → [Ваша компанія]**
2. Вкладка **"Податковий кабінет"**:
   - Шлях до ключа КЕП
   - Пароль ключа
   - РНОКПП/ЄДРПОУ

## Перевірка встановлення

Для перевірки коректності встановлення бібліотеки:

```python
import ctypes
import os

# Завантажуємо бібліотеку
lib_path = os.environ.get('IIT_LIB_PATH', '/opt/iit/eu/sw')
lib = ctypes.CDLL(f"{lib_path}/euscp.so")

# Ініціалізуємо
lib.EUSetUIMode(0)
err = lib.EUInitialize()
print(f"Initialize result: {err}")  # 0 = успішно

# Отримуємо версію
lib.EUGetVersion.restype = ctypes.c_char_p
version = lib.EUGetVersion()
print(f"Library version: {version.decode() if version else 'N/A'}")

# Завершуємо
lib.EUFinalize()
```

## Можливі помилки та їх вирішення

### Помилка: "Library not found: /opt/iit/eu/sw/euscp.so"

```bash
# Перевірте наявність файлу
ls -la /opt/iit/eu/sw/euscp.so

# Якщо відсутній - завантажте бібліотеку заново
```

### Помилка: "error while loading shared libraries"

```bash
# Оновіть кеш бібліотек
sudo ldconfig

# Або запустіть з явним шляхом
LD_LIBRARY_PATH=/opt/iit/eu/sw:$LD_LIBRARY_PATH odoo-bin ...
```

### Помилка: "Initialization failed" або помилки сертифікатів

```bash
# Перевірте наявність CA сертифікатів
ls -la /opt/iit/certificates/

# Завантажте актуальний пакет CACertificates.p7b
```

### Помилка: "Failed to load private key"

1. Перевірте правильність пароля
2. Перевірте формат ключа (має бути підтримуваний)
3. Перевірте права доступу до файлу ключа

## Коди помилок IIT

| Код | Опис |
|-----|------|
| 0 | Успішно |
| 1 | Помилка ініціалізації |
| 2 | Невірний пароль |
| 3 | Ключ не знайдено |
| 4 | Сертифікат не знайдено |
| 5 | Помилка підпису |
| 6 | Помилка перевірки підпису |
| 7 | Помилка шифрування |
| 8 | Помилка розшифрування |

## Посилання

- **IIT Downloads:** https://iit.com.ua/downloads
- **Документація IIT:** https://iit.com.ua/documentation
- **АЦСК ІДД ДПС:** https://acskidd.gov.ua/
- **Електронний кабінет:** https://cabinet.tax.gov.ua/

## Docker

Для використання в Docker-контейнері:

```dockerfile
FROM odoo:19.0

# Встановлюємо залежності
RUN apt-get update && apt-get install -y \
    libssl-dev \
    libcurl4-openssl-dev \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Завантажуємо та встановлюємо IIT бібліотеку
RUN mkdir -p /opt/iit/eu/sw /opt/iit/certificates \
    && cd /tmp \
    && wget -q https://iit.com.ua/download/productfiles/EUSignCP-Linux-20241205.zip \
    && unzip -q EUSignCP-Linux-20241205.zip \
    && cp -r EUSignCP-Linux/sw/x64/* /opt/iit/eu/sw/ \
    && rm -rf /tmp/EUSignCP-Linux* \
    && chmod -R 755 /opt/iit/eu/sw

# Завантажуємо CA сертифікати
RUN cd /opt/iit/certificates \
    && wget -q https://acskidd.gov.ua/download/CACertificates.p7b

# Налаштовуємо шлях до бібліотеки
RUN echo "/opt/iit/eu/sw" > /etc/ld.so.conf.d/iit.conf && ldconfig

# Змінні середовища
ENV IIT_LIB_PATH=/opt/iit/eu/sw
ENV IIT_CERT_PATH=/opt/iit/certificates
```

## Ліцензія

LGPL-3.0
