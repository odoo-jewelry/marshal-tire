"""Minimal pure-Python DBase III/IV reader.

Підтримує тільки те, що нам треба для виписок ДКСУ:
* Типи полів: C (char), N (numeric), D (date), L (logical), F (float)
* Memo поля (M, BLOB) — пропускаються
* Кодування — налаштовується (CP866 за замовчуванням, як у DBase III)

Цей читач **не** є повноцінною реалізацією специфікації DBF. Якщо знадобиться
складніший формат — встановіть `dbfread` (https://pypi.org/project/dbfread/)
і переозначте `read_dbf_records()` у клієнтському модулі.
"""
import struct
from datetime import date


class DbfReadError(Exception):
    pass


def _decode(buf: bytes, encoding: str) -> str:
    try:
        return buf.rstrip(b'\x00 ').decode(encoding)
    except UnicodeDecodeError:
        return buf.rstrip(b'\x00 ').decode(encoding, errors='replace')


def _parse_value(raw: bytes, ftype: str, encoding: str):
    """Convert raw DBF field bytes into a Python value based on field type."""
    text = _decode(raw, encoding).strip()
    if not text:
        return None
    if ftype == 'C':
        return text
    if ftype in ('N', 'F'):
        try:
            return float(text) if '.' in text else int(text)
        except ValueError:
            return None
    if ftype == 'D':  # YYYYMMDD
        if len(text) == 8 and text.isdigit():
            try:
                return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
            except ValueError:
                return None
        return None
    if ftype == 'L':
        return text.upper() in ('T', 'Y', '1')
    return text  # unknown type — return as string


def read_dbf_records(file_bytes: bytes, encoding: str = 'cp866'):
    """Iterate records from a DBF file as dicts {field_name: value}.

    `file_bytes` — raw .dbf content (e.g. from a Binary field).
    Skips memo blocks and the EOF marker. Yields one dict per non-deleted record.
    """
    if len(file_bytes) < 32:
        raise DbfReadError('Файл закороткий, щоб бути DBF.')

    # === Header (first 32 bytes) ===
    # version(1) + last update YMD(3) + record count(4 le) + header_len(2 le)
    #   + record_len(2 le) + reserved(20)
    version = file_bytes[0]
    if version not in (0x03, 0x04, 0x05, 0x83, 0x8b, 0xf5, 0x30):
        # Common DBase III/IV/FoxPro markers. We allow others with a warning.
        pass
    n_records = struct.unpack('<I', file_bytes[4:8])[0]
    header_len = struct.unpack('<H', file_bytes[8:10])[0]
    record_len = struct.unpack('<H', file_bytes[10:12])[0]

    # === Field descriptors (32 bytes each, until terminator 0x0D) ===
    fields = []
    pos = 32
    while pos < header_len and file_bytes[pos] != 0x0D:
        if pos + 32 > len(file_bytes):
            raise DbfReadError('Несподіваний кінець заголовка DBF.')
        descriptor = file_bytes[pos:pos + 32]
        name = descriptor[0:11].rstrip(b'\x00').decode('ascii', errors='replace').strip()
        ftype = chr(descriptor[11])
        length = descriptor[16]
        decimals = descriptor[17]
        fields.append({'name': name, 'type': ftype, 'len': length, 'dec': decimals})
        pos += 32

    if not fields:
        raise DbfReadError('Не знайдено опис полів DBF.')

    # === Records ===
    rec_pos = header_len
    for _ in range(n_records):
        if rec_pos + record_len > len(file_bytes):
            break  # truncated file — stop gracefully
        record = file_bytes[rec_pos:rec_pos + record_len]
        rec_pos += record_len
        if not record:
            break
        # First byte: 0x20 = active, 0x2A = deleted, 0x1A = EOF
        marker = record[0]
        if marker == 0x1A:
            break
        if marker == 0x2A:
            continue  # deleted record — skip
        # Parse fields
        offset = 1
        row = {}
        for f in fields:
            raw = record[offset:offset + f['len']]
            row[f['name']] = _parse_value(raw, f['type'], encoding)
            offset += f['len']
        yield row
