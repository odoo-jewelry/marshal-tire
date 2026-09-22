"""Tests for budget reports — render to HTML without errors."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'l10n_ua_budget_reports')
class TestBudgetReports(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kekv_2111 = cls.env.ref('l10n_ua_budget_base.kekv_2111')
        cls.kekv_2273 = cls.env.ref('l10n_ua_budget_base.kekv_2273')
        cls.kpkvk = cls.env.ref('l10n_ua_budget_base.kpkvk_2201190_2025')
        cls.estimate = cls.env['l10n_ua.budget.estimate'].create({
            'title': 'TEST estimate for report',
            'year': 2025,
            'fund_type': 'both',
            'kpkvk_id': cls.kpkvk.id,
            'line_ids': [
                (0, 0, {
                    'kekv_id': cls.kekv_2111.id, 'fund_type': 'general',
                    'm01': 1000, 'm06': 2000, 'm12': 3000,
                }),
                (0, 0, {
                    'kekv_id': cls.kekv_2273.id, 'fund_type': 'special',
                    'm03': 500, 'm09': 800,
                }),
            ],
        })
        cls.estimate.action_submit()
        cls.estimate.action_approve()

    def test_estimate_pdf_renders(self):
        """The kostorys QWeb template should render to HTML without exceptions."""
        report = self.env.ref('l10n_ua_budget_reports.action_report_budget_estimate')
        html, _content_type = report._render_qweb_html(report.report_name, self.estimate.ids)
        self.assertIn(b'KOSHTORYS' if False else 'КОШТОРИС', html.decode() if isinstance(html, bytes) else html)
        self.assertIn('Загальний фонд', html.decode() if isinstance(html, bytes) else html)
        self.assertIn('Спеціальний фонд', html.decode() if isinstance(html, bytes) else html)

    def test_form_2d_wizard_dates(self):
        wizard = self.env['l10n_ua.budget.form_2d.wizard'].create({
            'estimate_id': self.estimate.id,
            'period': 'q2',
        })
        self.assertEqual(str(wizard.date_from), '2025-04-01')
        self.assertEqual(str(wizard.date_to), '2025-06-30')

    def test_form_2d_wizard_year(self):
        wizard = self.env['l10n_ua.budget.form_2d.wizard'].new({
            'estimate_id': self.estimate.id,
            'period': 'year',
        })
        wizard._compute_dates()
        self.assertEqual(str(wizard.date_from), '2025-01-01')
        self.assertEqual(str(wizard.date_to), '2025-12-31')

    def test_form_2d_report_data(self):
        wizard = self.env['l10n_ua.budget.form_2d.wizard'].create({
            'estimate_id': self.estimate.id,
            'period': 'year',
        })
        rows = wizard.get_report_data()
        # Only 1 general-fund line (КЕКВ 2111), with planned = 6000
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['kekv_code'], '2111')
        self.assertEqual(rows[0]['plan'], 6000.0)

    def test_form_2d_plan_follows_the_period(self):
        """Той самий фікс, що й у мультиформі: план за період, а не річний.

        Кошторис: 1000 у січні, 2000 у червні, 3000 у грудні. За II квартал
        план — рівно 2000, тоді як річний дав би 6000 і «% виконання» втричі
        занижений.
        """
        wizard = self.env['l10n_ua.budget.form_2d.wizard'].create({
            'estimate_id': self.estimate.id,
            'period': 'q2',
        })

        rows = wizard.get_report_data()

        self.assertEqual(rows[0]['plan'], 2000.0)

    def test_form_2d_wizard_action_returns_report(self):
        """Wizard's action_print should return a report action dict."""
        # Без макета документа report_action() для адміна повертає не звіт, а
        # майстер налаштування макета (ir_actions_report.py:1179). У бойовій базі
        # макет заданий, у чистій тестовій — ні, тож задаємо його явно, інакше
        # тест перевіряє стан компанії, а не поведінку майстра.
        self.env.company.external_report_layout_id = self.env.ref('web.external_layout_standard')
        wizard = self.env['l10n_ua.budget.form_2d.wizard'].create({
            'estimate_id': self.estimate.id,
            'period': 'year',
        })
        result = wizard.action_print()
        self.assertEqual(result.get('type'), 'ir.actions.report')
        self.assertEqual(result.get('report_name'),
                          'l10n_ua_budget_reports.budget_form_2d_template')
        # data dict should be propagated
        self.assertEqual(result.get('data', {}).get('estimate_id'), self.estimate.id)
