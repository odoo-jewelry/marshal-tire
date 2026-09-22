"""Тести доходу в натуральній формі та gross-up ПДФО/ВЗ (#153).

Натуральний коефіцієнт (п. 164.5 ПКУ): К = 100 / (100 − ставка ПДФО).
При 18% → 1.2195122. Дохід у натуральній формі приводиться до "брутто"
перед оподаткуванням ПДФО і (за замовчуванням) військовим збором; ЄСВ —
від звичайної вартості без гросс-апу.
"""

from datetime import date

from .common import SalaryTestCase
from odoo.tests import tagged

COEF = 100.0 / 82.0  # 1.2195122


@tagged('post_install', '-at_install')
class TestInKindIncome(SalaryTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.inkind_type = cls.env['hr.accrual.type'].search(
            [('code', '=', 'INKIND')], limit=1)

    def _payslip_with(self, wage_amount, inkind_amount, inkind=True):
        """Листок: звичайний оклад (понад межу доходу — ПСП не діє) + натурдохід."""
        slip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
        })
        Accrual = self.env['hr.payslip.accrual']
        Accrual.create({
            'payslip_id': slip.id,
            'accrual_type_id': self.accrual_wage.id,
            'amount': wage_amount,
        })
        Accrual.create({
            'payslip_id': slip.id,
            'accrual_type_id': (self.inkind_type if inkind
                                else self.accrual_wage).id,
            'amount': inkind_amount,
        })
        return slip

    def test_gross_up_pdfo_base(self):
        slip = self._payslip_with(50000.0, 1000.0)
        # Понад межу доходу → ПСП = 0.
        self.assertEqual(slip.psp_amount, 0.0)
        # ПДФО-база = 50000 + 1000×К.
        self.assertAlmostEqual(slip.pdfo_base, 50000.0 + 1000.0 * COEF, places=2)
        self.assertAlmostEqual(
            slip.pdfo_amount, round((50000.0 + 1000.0 * COEF) * 0.18, 2), places=2)

    def test_gross_up_military_base(self):
        slip = self._payslip_with(50000.0, 1000.0)
        # За замовч. натур. коеф. застосовується і до ВЗ.
        self.assertAlmostEqual(
            slip.military_tax_base, 50000.0 + 1000.0 * COEF, places=2)

    def test_gross_salary_is_nominal(self):
        slip = self._payslip_with(50000.0, 1000.0)
        # Валовий дохід — за номіналом, без гросс-апу.
        self.assertAlmostEqual(slip.gross_salary, 51000.0, places=2)

    def test_esv_uses_nominal(self):
        slip = self._payslip_with(50000.0, 1000.0)
        # ЄСВ-база — від звичайної вартості (51000), а не грос-ап (51219.51).
        self.assertAlmostEqual(slip.esv_base, 51000.0, places=2)

    def test_no_gross_up_for_ordinary_income(self):
        # Той самий 1000, але звичайним нарахуванням — без коефіцієнта.
        slip = self._payslip_with(50000.0, 1000.0, inkind=False)
        self.assertAlmostEqual(slip.pdfo_base, 51000.0, places=2)

    def test_military_toggle_off(self):
        self.psp_params.natural_coef_for_military = False
        slip = self._payslip_with(50000.0, 1000.0)
        # ВЗ-база — за номіналом, ПДФО-база — все одно з коефіцієнтом.
        self.assertAlmostEqual(slip.military_tax_base, 51000.0, places=2)
        self.assertAlmostEqual(slip.pdfo_base, 50000.0 + 1000.0 * COEF, places=2)
