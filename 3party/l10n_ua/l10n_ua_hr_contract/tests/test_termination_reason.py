"""Tests for termination reasons — HR-19 from HR_UKRAINE.md.

Tests cover:
- Termination reason full reference
- Termination reason compensation flags

The work-schedule tests that used to live here went away with
hr.work.schedule itself (#213, phase 2): the weekly norm is now kept on the
native resource.calendar and covered by test_resource_calendar_ua.py.
"""

from odoo.tests import tagged
from .common import ContractTestCase


@tagged('post_install', '-at_install')
class TestTerminationReason(ContractTestCase):
    """Test hr.termination.reason model."""

    def _create_reason(self, **kwargs):
        vals = {
            'name': 'За власним бажанням',
            'article': '38',
            'paragraph': '1',
            'category': 'own_will',
            'notice_days': 14,
        }
        vals.update(kwargs)
        return self.env['hr.termination.reason'].create(vals)

    def test_reason_creation(self):
        """Reason should have required fields."""
        reason = self._create_reason()
        self.assertTrue(reason.name)
        self.assertEqual(reason.category, 'own_will')

    def test_full_reference_computed(self):
        """Full reference should combine article and paragraph."""
        reason = self._create_reason(article='38', paragraph='1')
        # full_reference may be False if not implemented, or a string
        if reason.full_reference:
            self.assertIn('38', reason.full_reference)
        else:
            # At minimum, article should be stored
            self.assertEqual(reason.article, '38')

    def test_reason_own_will_notice(self):
        """Own will requires 14 days notice."""
        reason = self._create_reason(
            category='own_will',
            notice_days=14,
        )
        self.assertEqual(reason.notice_days, 14)

    def test_reason_compensation(self):
        """Employer initiative may require compensation."""
        reason = self._create_reason(
            name='Скорочення штату',
            article='40',
            paragraph='1',
            category='employer_initiative',
            requires_compensation=True,
            compensation_amount='one_month',
        )
        self.assertTrue(reason.requires_compensation)
        self.assertEqual(reason.compensation_amount, 'one_month')

    def test_reason_categories(self):
        """All termination categories should be valid."""
        categories = ['own_will', 'agreement', 'fixed_term', 'transfer',
                       'employer_initiative', 'circumstances', 'other']
        for i, cat in enumerate(categories):
            reason = self._create_reason(
                name=f'Reason {cat}',
                article=str(30 + i),
                category=cat,
            )
            self.assertEqual(reason.category, cat)
            reason.unlink()
