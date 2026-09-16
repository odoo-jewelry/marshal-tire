from copy import deepcopy

from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged
from odoo.tools.safe_eval import safe_eval

from ..models.utils import CORRECTION_INTERNAL_TOKEN
from .common import PosOrderCorrectionCommon


@tagged("post_install", "-at_install")
class TestPosOrderCorrectionViews(PosOrderCorrectionCommon):
    def _order_arch(self):
        view = self.env["pos.order"].get_view(
            self.env.ref("point_of_sale.view_pos_pos_form").id, "form"
        )
        return etree.fromstring(view["arch"])

    def _visible_receipt_pages(self, order):
        values = {
            "correction_has_applied": order.correction_has_applied,
            "is_correction_order": order.is_correction_order,
        }
        names = {"products", "payments", "correction_products", "correction_payments"}
        return [
            page.get("name") for page in self._order_arch().xpath("//sheet/notebook/page")
            if page.get("name") in names
            and not safe_eval(page.get("invisible", "False"), values)
        ]

    def _apply(self, order, **values):
        correction = self._prepare(order)
        correction.reason = "Correct receipt presentation"
        if "qty" in values:
            correction.line_ids.qty = values["qty"]
        if "price" in values:
            correction.line_ids.price_unit = values["price"]
        if "method" in values:
            correction.payment_ids.payment_method_id = values["method"]
        correction.payment_ids.amount = values["amount"]
        self.assertEqual(correction.action_apply()["res_id"], order.id)
        return correction

    def _rows(self, details, index):
        table = etree.HTML(str(details)).xpath("//table")[index]
        return [["".join(cell.itertext()) for cell in row] for row in table.xpath("tbody/tr")]

    def test_working_tabs_select_applied_result_and_preserve_ordinary_orders(self):
        order = self._create_paid_order("correction-view-modes")
        standard = ["products", "payments"]
        current = ["correction_products", "correction_payments"]
        self.assertEqual(self._visible_receipt_pages(order), standard)
        preparation = self._prepare(order)
        preparation.line_ids.price_unit = 120
        self.assertEqual(self._visible_receipt_pages(order), standard)
        preparation.action_cancel()
        self.assertEqual(self._visible_receipt_pages(order), standard)

        correction = self._apply(order, method=self.bank_pm1, amount=100)
        self.assertEqual(self._visible_receipt_pages(order), current)
        self.assertEqual(order.correction_current_total, 100)
        self.assertEqual(order.correction_current_line_ids, order.lines)
        payment_rows = etree.HTML(str(order.correction_current_payments)).xpath("//tr")
        self.assertEqual(len(payment_rows), 1)
        self.assertIn(self.bank_pm1.name, "".join(payment_rows[0].itertext()))
        self.assertNotIn(self.cash_pm1.name, str(order.correction_current_payments))
        self.assertEqual(self._visible_receipt_pages(correction.applied_order_id), standard)
        self.assertEqual(correction.applied_order_id.amount_total, 0)
        self.assertTrue(order.correction_pending)

        draft = self._prepare(order)
        draft.line_ids.price_unit = 999
        draft.payment_ids.amount = 999
        self.assertEqual(order.correction_current_total, 100)
        draft.action_cancel()
        self.assertEqual(self._visible_receipt_pages(order), current)
        empty = self._prepare(order)
        empty.reason = "No sale"
        empty.line_ids.unlink()
        empty.payment_ids.unlink()
        empty.action_apply()
        self.assertEqual(self._visible_receipt_pages(order), current)
        self.assertFalse(order.correction_current_line_ids)
        self.assertEqual(order.correction_current_total, 0)
        self.assertFalse(etree.HTML(str(order.correction_current_payments)).xpath("//tr"))

        ordinary = self._create_paid_order("correction-view-ordinary")
        for state in ("draft", "cancel"):
            source = ordinary.copy({"state": state})
            self.assertEqual(self._visible_receipt_pages(source), standard)
            self.assertEqual(source.lines.qty, 1)
        refund = ordinary._refund()
        self.assertEqual(self._visible_receipt_pages(refund), standard)
        self.assertEqual(refund.lines.qty, -1)

    def test_history_and_navigation_across_four_revisions(self):
        order = self._create_paid_order("correction-view-four-revisions")
        original = order.read(["date_order", "session_id", "amount_total", "lines", "payment_ids"])
        first = self._apply(order, price=110, amount=110)
        second = self._apply(order, qty=2, amount=220)
        before = deepcopy(second.before_snapshot)
        after = deepcopy(second.after_snapshot)
        second_details = second.before_details, second.after_details
        third = self._apply(order, method=self.bank_pm1, amount=220)
        fourth_draft = self._prepare(order)
        fourth_draft.reason = "Fix the quantity from the second correction"
        fourth_draft.line_ids.qty = 1
        fourth_draft.payment_ids.amount = 110
        self.assertEqual(self._prepare(order), fourth_draft)
        self.assertEqual(fourth_draft.payment_ids.payment_method_id, self.bank_pm1)
        self.assertEqual(fourth_draft.line_ids.price_unit, 110)
        self.assertEqual(fourth_draft.action_apply()["res_id"], order.id)
        self.assertEqual(order.correction_current_total, 110)
        self.assertEqual(order.correction_current_line_ids.qty, 1)
        self.assertEqual(order.correction_count, 4)
        self.assertEqual(order.read(list(original[0].keys() - {"id"})), original)
        self.assertEqual(order.lines.price_unit, 100)
        self.assertEqual(order.payment_ids.payment_method_id, self.cash_pm1)
        self.assertEqual(order.payment_ids.amount, 100)
        self.assertEqual(second.before_snapshot, before)
        self.assertEqual(second.after_snapshot, after)
        self.assertEqual((second.before_details, second.after_details), second_details)
        self.assertEqual(self._rows(second.before_details, 0)[0][1], "1")
        self.assertEqual(self._rows(second.after_details, 0)[0][1], "2")
        self.assertIn(self.cash_pm1.name, self._rows(second.after_details, 1)[0][0])
        self.assertIn(self.bank_pm1.name, self._rows(third.after_details, 1)[0][0])

        documents = order.correction_order_ids
        payments = documents.payment_ids
        pickings = documents.picking_ids
        self.assertEqual(first.action_apply()["res_id"], order.id)
        self.assertEqual(order.correction_order_ids, documents)
        self.assertEqual(documents.payment_ids, payments)
        self.assertEqual(documents.picking_ids, pickings)
        self.assertEqual(first.action_open_applied_order()["res_id"], first.applied_order_id.id)
        self.assertEqual(first.applied_order_id.action_open_current_receipt()["res_id"], order.id)
        self.assertEqual(second.action_open_current_receipt()["res_id"], order.id)
        with self.assertRaises(UserError):
            second.line_ids.qty = 9

    def test_history_handles_missing_values_zero_and_escaped_text(self):
        order = self._create_paid_order("correction-view-legacy")
        correction = self._apply(order, price=110, amount=110)
        snapshot = deepcopy(correction.after_snapshot)
        snapshot["lines"][0].pop("discount")
        snapshot["lines"][0]["qty"] = 0
        snapshot["lines"][0]["price_unit"] = 0
        snapshot["lines"][0]["product_id"] = 2147483647
        snapshot["lines"][0]["lot_names"] = '<script>alert("lot")</script>'
        snapshot["lines"][0]["custom_attribute_values"] = [{
            "custom_product_template_attribute_value_id": 2147483647,
            "custom_value": '<img src="x" onerror="alert(1)">',
        }]
        snapshot.pop("payments")
        correction.with_context(pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN).write({
            "before_snapshot": {"lines": [], "payments": []},
            "after_snapshot": snapshot,
        })
        details = correction.after_details
        cells = self._rows(details, 0)[0]
        self.assertEqual(cells[0], "Not recorded or unavailable")
        self.assertEqual(cells[1], "0")
        self.assertEqual(cells[3], "Not recorded or unavailable")
        self.assertIn('<script>alert("lot")</script>', cells[5])
        self.assertIn('<img src="x" onerror="alert(1)">', cells[7])
        self.assertFalse(etree.HTML(str(details)).xpath("//script|//img"))
        self.assertIn("Not recorded or unavailable", str(details).split("Payments")[1])
        self.assertNotIn("Not recorded or unavailable", correction.before_details)
        self.assertFalse(etree.HTML(str(correction.before_details)).xpath("//table"))
        self.assertEqual(correction.after_snapshot, snapshot)
        snapshot["lines"][0]["price_unit"] = 0.123456
        snapshot["lines"][0]["qty"] = 0.00001
        correction.with_context(pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN).write({
            "after_snapshot": snapshot,
        })
        cells = self._rows(correction.after_details, 0)[0]
        self.assertEqual(cells[1:3], ["0.00001", "0.123456"])

    def test_history_and_actions_respect_reader_access(self):
        order = self._create_paid_order("correction-view-access")
        correction = self._apply(order, price=110, amount=110)
        cashier = new_test_user(
            self.env, login="correction_history_reader",
            groups="base.group_user,point_of_sale.group_pos_user",
            company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)],
        )
        readable = correction.with_user(cashier)
        self.assertIn(self.product100.name, readable.after_details)
        self.assertEqual(readable.action_open_current_receipt()["res_id"], order.id)
        self.assertEqual(order.with_user(cashier).action_open_correction_history()["domain"], [
            ("root_order_id", "=", order.id),
        ])
        with self.assertRaises(AccessError):
            readable.action_apply()
        with self.assertRaises(AccessError):
            order.with_user(cashier).action_prepare_correction()

        product_name = self.product100.name
        self.env["ir.rule"].create({
            "name": "Hide a history product", "model_id": self.env["ir.model"]._get_id("product.product"),
            "domain_force": repr([("id", "!=", self.product100.id)]),
        })
        readable.invalidate_recordset(["before_details", "after_details"])
        self.assertNotIn(product_name, readable.after_details)
        self.assertIn("Not recorded or unavailable", readable.after_details)

        other_company = self.env["res.company"].create({"name": "History Other Company"})
        cashier.company_ids = [Command.link(other_company.id)]
        foreign = correction.with_user(cashier).with_context(allowed_company_ids=other_company.ids)
        foreign_order = order.with_user(cashier).with_context(allowed_company_ids=other_company.ids)
        for action in (
            foreign.action_open_current_receipt, foreign.action_open_applied_order,
            foreign_order.action_open_current_receipt, foreign_order.action_open_correction_history,
        ):
            with self.assertRaises(AccessError):
                action()
        with self.assertRaises(AccessError):
            foreign.read(["before_details", "after_details"])

    def test_compiled_forms_keep_history_readonly_and_standard_extensions(self):
        arch = self._order_arch()
        self.assertFalse(arch.xpath("//page[@name='current_sale']"))
        self.assertEqual(arch.xpath("//page[@name='products']/@string"), ["Products"])
        self.assertEqual(arch.xpath("//page[@name='payments']/@string"), ["Payments"])
        original = arch.xpath("//page[@name='correction_history']/details[@name='original_receipt']")[0]
        for name in ("lines", "payment_ids", "date_order", "session_id", "amount_total"):
            self.assertEqual(original.xpath(".//field[@name=$name]/@readonly", name=name), ["1"])
        self.assertTrue(arch.xpath("//page[@name='customer_debt']"))
        self.assertTrue(arch.xpath("//widget[@name='web_ribbon'][@invisible='not correction_pending']"))
        self.assertTrue(arch.xpath("//div[@invisible='not correction_stock_pending']"))
        correction_view = self.env["pos.order.correction"].get_view(
            self.env.ref("pos_order_correction.view_pos_order_correction_form").id, "form"
        )
        comparison = etree.fromstring(correction_view["arch"])
        self.assertFalse(comparison.xpath("//field[@name='before_snapshot' or @name='after_snapshot']"))
        self.assertEqual(comparison.xpath("//page[@name='correction_comparison']//field/@name"), [
            "before_details", "after_details",
        ])
