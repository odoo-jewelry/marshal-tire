"""Multi-company rule presence test (issue #178).

Asserts each multi-company ir.rule exists and is global. Note: the flag is
read as rule['global'] — there is NO rule.global_ attribute.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMultiCompanyRules(TransactionCase):

    RULE_XMLIDS = [
        'l10n_ua_hr_holidays.hr_sick_leave_company_rule',
        'l10n_ua_hr_holidays.hr_vacation_schedule_company_rule',
        'l10n_ua_hr_holidays.hr_employee_vacation_summary_report_company_rule',
    ]

    def test_rules_exist_and_global(self):
        for xmlid in self.RULE_XMLIDS:
            rule = self.env.ref(xmlid)
            self.assertEqual(rule._name, 'ir.rule')
            self.assertTrue(
                rule['global'],
                "Rule %s must be global" % xmlid,
            )
