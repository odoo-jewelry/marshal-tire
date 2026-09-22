#!/usr/bin/env python3
"""Convert Ukrainian Classifier of Professions CSV to Odoo XML format."""

import csv
import re
import hashlib

INPUT_FILE = 'Класифікатор професій.csv'
OUTPUT_FILE = 'hr_kp2010_data.xml'

def clean_code(code):
    """Clean and normalize KP code."""
    if not code:
        return None
    code = code.strip().replace(' ', '')
    if not code:
        return None
    return code

def get_group_code(code):
    """Extract major group code (first digit)."""
    code_clean = code.replace('.', '')
    if code_clean and len(code_clean) >= 1:
        return code_clean[0]
    return None

def get_section_code(code):
    """Extract section code (first 2 digits)."""
    code_clean = code.replace('.', '')
    if code_clean and len(code_clean) >= 2:
        return code_clean[:2]
    return None

def make_xml_id(code, name, idx):
    """Generate a valid XML ID from code and name."""
    name_hash = hashlib.md5(name.encode('utf-8')).hexdigest()[:6]
    xml_id = f"kp_{code.replace('.', '_')}_{name_hash}"
    xml_id = re.sub(r'[^a-zA-Z0-9_]', '_', xml_id)
    return xml_id

def escape_xml(text):
    """Escape special XML characters."""
    if not text:
        return ''
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))

def main():
    records = []
    seen = set()
    idx = 0
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        header = next(reader)
        
        for row in reader:
            if len(row) < 5:
                continue
            
            code = clean_code(row[0])
            name = row[4].strip() if row[4] else ''
            
            if not code or not name:
                continue
            
            key = (code, name)
            if key in seen:
                continue
            seen.add(key)
            idx += 1
            
            records.append({
                'code': code,
                'name': name,
                'group_code': get_group_code(code),
                'section_code': get_section_code(code),
                'idx': idx,
            })
    
    records.sort(key=lambda x: (x['code'], x['name']))
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write('<odoo>\n')
        f.write('    <data noupdate="1">\n\n')
        
        for rec in records:
            xml_id = make_xml_id(rec['code'], rec['name'], rec['idx'])
            f.write(f'        <record id="{xml_id}" model="hr.kp2010">\n')
            f.write(f'            <field name="code">{escape_xml(rec["code"])}</field>\n')
            f.write(f'            <field name="name">{escape_xml(rec["name"])}</field>\n')
            if rec['group_code']:
                f.write(f'            <field name="group_code">{escape_xml(rec["group_code"])}</field>\n')
            if rec['section_code']:
                f.write(f'            <field name="section_code">{escape_xml(rec["section_code"])}</field>\n')
            f.write('        </record>\n\n')
        
        f.write('    </data>\n')
        f.write('</odoo>\n')
    
    print(f"Converted {len(records)} profession records to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
