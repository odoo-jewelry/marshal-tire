"""Мінімальний запис dBASE III (.dbf) для зарплатних банк-файлів (#152).

Без зовнішніх залежностей: формує заголовок, дескриптори полів і записи
згідно зі специфікацією dBASE III. Кирилиця пишеться у cp1251 (переважне
кодування українських банк-файлів); мовний драйвер у заголовку — 0xC9.
"""
import struct
from datetime import date


def build_dbf(field_defs, rows, encoding='cp1251', language_driver=0xC9):
    """Побудувати байти .dbf.

    :param field_defs: список кортежів (name, type, length, decimals):
        type 'C' — символьне, 'N' — числове, 'D' — дата (8 симв. YYYYMMDD).
    :param rows: список dict {field_name: value}.
    :param encoding: кодування тексту (cp1251 за замовчуванням).
    :return: bytes готового .dbf-файлу.
    """
    num_records = len(rows)
    num_fields = len(field_defs)
    header_len = 32 + 32 * num_fields + 1
    record_len = 1 + sum(length for (_n, _t, length, _d) in field_defs)

    out = bytearray()
    # --- Заголовок (32 байти) ---
    out += struct.pack('<B', 0x03)          # dBASE III without memo
    out += struct.pack('<BBB', 25, 1, 1)    # дата оновлення (детермінована)
    out += struct.pack('<I', num_records)
    out += struct.pack('<H', header_len)
    out += struct.pack('<H', record_len)
    out += b'\x00' * 17
    out += struct.pack('<B', language_driver)
    out += b'\x00' * 2

    # --- Дескриптори полів (по 32 байти) ---
    for (name, ftype, length, decimals) in field_defs:
        fname = name.encode('ascii')[:11]
        out += fname + b'\x00' * (11 - len(fname))
        out += ftype.encode('ascii')
        out += b'\x00' * 4                   # displacement
        out += struct.pack('<B', length)
        out += struct.pack('<B', decimals)
        out += b'\x00' * 14
    out += b'\x0D'                           # термінатор дескрипторів

    # --- Записи ---
    for row in rows:
        out += b'\x20'                       # прапорець видалення (не видалено)
        for (name, ftype, length, decimals) in field_defs:
            value = row.get(name, '')
            if ftype == 'N':
                if decimals:
                    text = f'{float(value or 0):.{decimals}f}'
                else:
                    text = str(int(value or 0))
                text = text[:length].rjust(length)
            elif ftype == 'D':
                if isinstance(value, date):
                    text = value.strftime('%Y%m%d')
                else:
                    text = (str(value or '')[:8]).ljust(8)
                text = text[:length].ljust(length)
            else:
                text = '' if value is None else str(value)
                encoded = text.encode(encoding, 'replace')[:length]
                out += encoded + b'\x20' * (length - len(encoded))
                continue
            out += text.encode(encoding, 'replace')[:length].ljust(length, b' ')
    out += b'\x1A'                           # EOF
    return bytes(out)
