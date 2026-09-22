"""Tests for personal file (особова справа) — HR-21,22 from HR_UKRAINE.md.

Tests cover:
- Personal file creation with auto-numbering
- Unique employee constraint
- Family members
- Document storage
- Work history entries
"""

from datetime import date
from psycopg2 import IntegrityError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestPersonalFile(TransactionCase):
    """Test hr.personal.file model."""

    _counter = 0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

    def _create_employee(self, name=None):
        TestPersonalFile._counter += 1
        if name is None:
            name = f'Test Employee PF {TestPersonalFile._counter}'
        return self.env['hr.employee'].create({
            'name': name,
            'company_id': self.company.id,
        })

    def _create_personal_file(self, employee=None, **kwargs):
        if employee is None:
            employee = self._create_employee()
        vals = {
            'employee_id': employee.id,
        }
        vals.update(kwargs)
        return self.env['hr.personal.file'].create(vals)

    def test_personal_file_creation(self):
        """Personal file should be created with auto file number."""
        pf = self._create_personal_file()
        self.assertTrue(pf.name)
        self.assertTrue(pf.employee_id)

    def test_personal_file_unique_employee(self):
        """One employee can have only one personal file."""
        emp = self._create_employee()
        self._create_personal_file(emp)
        # The unique(employee_id) is a database constraint: it fires at flush
        # and aborts the transaction. Wrap the failing insert in a savepoint
        # (so the transaction stays usable for teardown) and flush inside the
        # block so the IntegrityError is raised where assertRaises can catch
        # it. mute_logger silences the expected "bad query" error line.
        with self.assertRaises(IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.env.cr.savepoint():
            self._create_personal_file(emp)
            self.env.flush_all()

    def test_personal_file_family_members(self):
        """Should be able to add family members."""
        pf = self._create_personal_file()
        member = self.env['hr.personal.file.family'].create({
            'personal_file_id': pf.id,
            'name': 'Шевченко Олена Петрівна',
            'relation': 'spouse',
            'birth_date': date(1990, 5, 15),
        })
        self.assertEqual(len(pf.family_member_ids), 1)
        self.assertEqual(member.relation, 'spouse')

    def test_personal_file_documents(self):
        """Should be able to add documents."""
        pf = self._create_personal_file()
        doc = self.env['hr.personal.file.document'].create({
            'personal_file_id': pf.id,
            'document_type': 'passport',
            'name': 'Паспорт громадянина України',
            'number': 'АА123456',
            'date': date(2015, 3, 20),
            'issued_by': 'ТЦК м. Києва',
        })
        self.assertEqual(len(pf.document_ids), 1)
        self.assertEqual(doc.document_type, 'passport')

    def test_personal_file_document_types(self):
        """All document types should be valid."""
        pf = self._create_personal_file()
        types = ['passport', 'id_card', 'rnokpp', 'diploma',
                 'certificate', 'military', 'medical', 'photo', 'other']
        for i, dtype in enumerate(types):
            self.env['hr.personal.file.document'].create({
                'personal_file_id': pf.id,
                'document_type': dtype,
                'name': f'Doc {dtype}',
                'number': f'NUM-{i}',
            })
        self.assertEqual(len(pf.document_ids), len(types))

    def test_personal_file_work_history(self):
        """Should be able to add work history entries."""
        pf = self._create_personal_file()
        entry = self.env['hr.personal.file.work.history'].create({
            'personal_file_id': pf.id,
            'date_from': date(2020, 1, 15),
            'date_to': date(2024, 12, 31),
            'organization': 'ТОВ "Попередня компанія"',
            'position': 'Інженер',
            'entry_type': 'hire',
        })
        self.assertEqual(len(pf.work_history_ids), 1)
        self.assertEqual(entry.entry_type, 'hire')

    def test_two_employees_two_files(self):
        """Different employees can each have a file."""
        pf1 = self._create_personal_file()
        pf2 = self._create_personal_file()
        self.assertNotEqual(pf1.name, pf2.name)
