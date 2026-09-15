"""Run selected upstream stock regressions with this addon fully loaded."""

from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.test_pos_stock_account import TestPoSStock
from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.addons.stock_account.tests.test_stockvaluation import TestStockValuation
from odoo.addons.stock_account.tests.test_stockvaluationlayer import TestStockValuationFIFO


@tagged("post_install", "-at_install")
class TestStockRepairStandardFIFO(TestStockValuationFIFO):
    allow_inherited_tests_method = True


@tagged("post_install", "-at_install")
class TestStockRepairStandardPOS(TestPoSStock):
    allow_inherited_tests_method = True


@tagged("post_install", "-at_install")
class TestStockRepairStandardValuation(TestStockValuationCommon):
    test_edit_done_move = TestStockValuation.test_fifo_edit_done_move1
    test_manual_revaluation = TestStockValuation.test_fifo_manual_revaluation
