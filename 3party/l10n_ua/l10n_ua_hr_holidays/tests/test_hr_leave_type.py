from odoo.tests.common import TransactionCase


class TestHrLeaveType(TransactionCase):
    """Tests for hr.leave.type Ukrainian extensions"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.leave_type = cls.env['hr.leave.type'].create({
            'name': 'Test Annual Leave',
            'ua_leave_category': 'annual_basic',
            'annual_days': 24,
            'is_calendar_days': True,
            'is_transferable': True,
            'max_transfer_days': 12,
            'requires_experience': True,
            'min_experience_months': 6,
            'is_paid': True,
            'payment_source': 'employer',
            'min_continuous_days': 14,
        })

    def test_leave_type_creation(self):
        """Test that leave type is created with UA fields"""
        self.assertEqual(self.leave_type.ua_leave_category, 'annual_basic')
        self.assertEqual(self.leave_type.annual_days, 24)
        self.assertTrue(self.leave_type.is_calendar_days)
        self.assertTrue(self.leave_type.is_transferable)
        self.assertEqual(self.leave_type.max_transfer_days, 12)
        self.assertTrue(self.leave_type.requires_experience)
        self.assertEqual(self.leave_type.min_experience_months, 6)
        self.assertTrue(self.leave_type.is_paid)
        self.assertEqual(self.leave_type.payment_source, 'employer')
        self.assertEqual(self.leave_type.min_continuous_days, 14)

    def test_leave_type_defaults(self):
        """Test default values for leave type"""
        leave_type = self.env['hr.leave.type'].create({
            'name': 'Test Default Leave',
        })
        self.assertTrue(leave_type.is_calendar_days)
        self.assertTrue(leave_type.is_transferable)
        self.assertEqual(leave_type.annual_days, 24)
        self.assertEqual(leave_type.min_experience_months, 6)
        self.assertTrue(leave_type.is_paid)
        self.assertEqual(leave_type.payment_source, 'employer')
        self.assertEqual(leave_type.min_continuous_days, 14)

    def test_leave_type_categories(self):
        """Test all UA leave categories can be set"""
        categories = [
            'annual_basic', 'annual_additional', 'educational', 'creative',
            'social', 'unpaid', 'maternity', 'childcare', 'sick', 'other'
        ]
        for category in categories:
            leave_type = self.env['hr.leave.type'].create({
                'name': f'Test {category}',
                'ua_leave_category': category,
            })
            self.assertEqual(leave_type.ua_leave_category, category)

    def test_payment_sources(self):
        """Test all payment sources can be set"""
        sources = ['employer', 'fss', 'mixed']
        for source in sources:
            leave_type = self.env['hr.leave.type'].create({
                'name': f'Test {source}',
                'payment_source': source,
            })
            self.assertEqual(leave_type.payment_source, source)

    def test_default_leave_type_single_no_conflict(self):
        """Setting a default with no existing default via checkbox."""
        company = self.env.company
        lt = self.env['hr.leave.type'].create({
            'name': 'Default A', 'company_id': company.id})
        lt.write({'ua_is_default': True})
        self.assertTrue(lt.ua_is_default)

    def test_default_leave_type_conflict_auto_resolves(self):
        """Setting a second default automatically clears the previous one."""
        company = self.env.company
        lt_a = self.env['hr.leave.type'].create({
            'name': 'Default A', 'company_id': company.id})
        lt_b = self.env['hr.leave.type'].create({
            'name': 'Default B', 'company_id': company.id})
        lt_a.write({'ua_is_default': True})
        self.assertTrue(lt_a.ua_is_default)
        # Setting lt_b as default automatically clears lt_a
        lt_b.write({'ua_is_default': True})
        self.assertTrue(lt_b.ua_is_default)
        self.assertFalse(lt_a.ua_is_default)

    def test_default_leave_type_unset(self):
        """Unsetting a default via checkbox."""
        company = self.env.company
        lt = self.env['hr.leave.type'].create({
            'name': 'Default A', 'company_id': company.id})
        lt.write({'ua_is_default': True})
        lt.write({'ua_is_default': False})
        self.assertFalse(lt.ua_is_default)
