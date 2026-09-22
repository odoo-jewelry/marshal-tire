"""Military accounting covers citizens of Ukraine only (#158).

Art. 1 of Law No 2232-XII puts the military duty on citizens of Ukraine, so a
foreign national has no register category. The nationality is the core field
`hr.version.country_id` ("Nationality (Country)") — no citizenship field of
our own.
"""

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import TestHrUaBase


@tagged('post_install', '-at_install')
class TestMilitaryCitizenship(TestHrUaBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ukraine = cls.env.ref('base.ua')
        cls.poland = cls.env.ref('base.pl')

    def test_applicable_without_nationality(self):
        """An empty nationality counts as Ukrainian: it is rarely filled in,
        and hiding the block from every such card would be worse."""
        employee = self._create_employee()
        self.assertFalse(employee.country_id)
        self.assertTrue(employee.military_accounting_applicable)

    def test_applicable_for_ukrainian_citizen(self):
        employee = self._create_employee(country_id=self.ukraine.id)
        self.assertTrue(employee.military_accounting_applicable)

    def test_not_applicable_for_foreign_national(self):
        employee = self._create_employee(country_id=self.poland.id)
        self.assertFalse(employee.military_accounting_applicable)

    def test_foreign_national_cannot_be_registered(self):
        employee = self._create_employee(country_id=self.poland.id)
        with self.assertRaises(ValidationError):
            employee.military_register_category = 'liable'

    def test_changing_nationality_rejects_existing_registration(self):
        """The check also fires from the other side — putting a foreign
        nationality on a card that carries a register category."""
        employee = self._create_employee(military_register_category='liable')
        with self.assertRaises(ValidationError):
            employee.country_id = self.poland.id

    def test_not_applicable_category_is_always_allowed(self):
        employee = self._create_employee(country_id=self.poland.id)
        employee.military_register_category = 'not_applicable'
        self.assertEqual(employee.military_register_category, 'not_applicable')
