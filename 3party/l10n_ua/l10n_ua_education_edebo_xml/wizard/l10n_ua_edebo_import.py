"""XML parser for ЄДЕБО exchange.

Реальна XSD-схема ЄДЕБО закрита і змінюється МОНом. Цей плагін реалізує
гнучкий парсер, який терпимий до варіацій тегів — переозначте
`_edebo_xml_extract_persons()` у дочірньому модулі для конкретного формату.
"""
from datetime import datetime
from xml.etree import ElementTree as ET

from odoo import models, _
from odoo.exceptions import UserError


# Поширені синоніми тегів (нечутливі до регістру). Зустрічаються в реальних
# обміннях з ЄДЕБО.
TAG_SYNONYMS = {
    'student': ['student', 'person', 'osoba', 'student-record', 'учасник'],
    'last_name': ['last_name', 'lastname', 'surname', 'family_name', 'prizvyshche'],
    'first_name': ['first_name', 'firstname', 'name', 'given_name', "im'ia"],
    'middle_name': ['middle_name', 'middlename', 'patronymic', 'po_batkovi'],
    'birthdate': ['birthdate', 'birth_date', 'birthday', 'dob', 'data_nar'],
    'rnokpp': ['rnokpp', 'tax_id', 'ipn', 'inn'],
    'student_number': ['student_number', 'student_no', 'card_no', 'record_no', 'edebo_id'],
    'member_type': ['member_type', 'type', 'category'],
}


def _norm(tag: str) -> str:
    """Strip XML namespace + lowercase for matching."""
    return tag.split('}', 1)[-1].lower()


def _find_child_value(element, candidates):
    """Find the first child element whose tag matches one of `candidates`.

    Returns the stripped text or empty string.
    """
    cand_set = {c.lower() for c in candidates}
    for child in element:
        if _norm(child.tag) in cand_set:
            return (child.text or '').strip()
    return ''


class L10nUaEdeboImport(models.TransientModel):
    _inherit = 'l10n_ua.edebo.import'

    def _parse_custom(self, content):
        """XML override of the ЄДЕБО import wizard."""
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            raise UserError(_('Невалідний XML: %s', str(e)))

        persons = self._edebo_xml_extract_persons(root)
        if not persons:
            raise UserError(_(
                'У XML не знайдено жодного запису учня/студента. '
                'Перевірте структуру файлу або переозначте '
                '_edebo_xml_extract_persons() у дочірньому модулі.'))
        return persons

    def _edebo_xml_extract_persons(self, root):
        """Walk the tree and pull person records into the wizard's canonical shape.

        Перевизначити у дочірньому модулі для специфічного формату МОН.
        """
        out = []
        student_tags = {t.lower() for t in TAG_SYNONYMS['student']}

        # Strategy: do a depth-first walk and yield any element whose tag
        # matches a known "student" synonym.
        for elem in root.iter():
            if _norm(elem.tag) not in student_tags:
                continue
            last_name = _find_child_value(elem, TAG_SYNONYMS['last_name'])
            first_name = _find_child_value(elem, TAG_SYNONYMS['first_name'])
            middle_name = _find_child_value(elem, TAG_SYNONYMS['middle_name'])
            birth_str = _find_child_value(elem, TAG_SYNONYMS['birthdate'])
            rnokpp = _find_child_value(elem, TAG_SYNONYMS['rnokpp'])
            student_no = _find_child_value(elem, TAG_SYNONYMS['student_number'])
            member_type = _find_child_value(elem, TAG_SYNONYMS['member_type']) or 'student'

            if not (last_name and first_name):
                continue  # skip incomplete

            # Parse birthdate
            birthdate = None
            for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%Y/%m/%d'):
                try:
                    birthdate = datetime.strptime(birth_str, fmt).date()
                    break
                except ValueError:
                    continue

            full_name = f"{last_name} {first_name}".strip()
            if middle_name:
                full_name += f" {middle_name}"

            out.append({
                'name': full_name,
                'birthdate': birthdate,
                'member_type': member_type,
                'student_number': student_no or False,
                'rnokpp': rnokpp or False,
            })
        return out
