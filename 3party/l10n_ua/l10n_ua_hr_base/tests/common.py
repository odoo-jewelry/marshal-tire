# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase
from datetime import date
from dateutil.relativedelta import relativedelta


class TestHrUaBase(TransactionCase):
    """Common test class for Ukrainian HR Base module."""

    _rnokpp_counter = 0  # Class-level counter for unique RNOKPP generation

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test company
        cls.company = cls.env['res.company'].create({
            'name': 'Test UA Company',
        })

        # Create test department
        cls.department = cls.env['hr.department'].create({
            'name': 'Test Department',
            'company_id': cls.company.id,
        })

        # Create test job position
        cls.job = cls.env['hr.job'].create({
            'name': 'Test Position',
            'company_id': cls.company.id,
            'department_id': cls.department.id,
        })

        # Valid RNOKPP examples (with correct checksum)
        cls.valid_rnokpp_1 = '3184710691'  # Valid checksum
        cls.valid_rnokpp_2 = '2222222225'  # Valid checksum

        # Invalid RNOKPP examples
        cls.invalid_rnokpp_checksum = '1234567890'  # Wrong checksum
        cls.invalid_rnokpp_length = '123456789'  # Too short
        cls.invalid_rnokpp_letters = '123456789A'  # Contains letters

    @classmethod
    def get_unique_rnokpp(cls):
        """Generate a unique valid RNOKPP for testing."""
        cls._rnokpp_counter += 1
        base = str(100000000 + cls._rnokpp_counter).zfill(9)
        return cls.generate_valid_rnokpp(base)

    def _create_employee(self, **kwargs):
        """Helper method to create test employee."""
        vals = {
            'name': 'Test Employee',
            'company_id': self.company.id,
            'department_id': self.department.id,
            'job_id': self.job.id,
        }
        vals.update(kwargs)
        return self.env['hr.employee'].create(vals)

    @staticmethod
    def generate_valid_rnokpp(base_digits):
        """Generate a valid RNOKPP with correct checksum.

        Args:
            base_digits: String of 9 digits

        Returns:
            String of 10 digits with valid checksum
        """
        if len(base_digits) != 9 or not base_digits.isdigit():
            raise ValueError("Base must be exactly 9 digits")

        weights = [-1, 5, 7, 9, 4, 6, 10, 5, 7]
        checksum = sum(int(base_digits[i]) * weights[i] for i in range(9))
        control = (checksum % 11) % 10
        return base_digits + str(control)
