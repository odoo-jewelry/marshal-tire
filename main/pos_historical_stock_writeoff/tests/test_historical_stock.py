from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time
from lxml import etree

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, tagged
from odoo.tests.common import new_test_user

from odoo.addons.pos_order_correction.tests.common import PosOrderCorrectionCommon


@tagged("post_install", "-at_install")
class TestHistoricalStock(PosOrderCorrectionCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids = [Command.link(cls.env.ref("pos_historical_stock_writeoff.group_historical_stock").id)]
        cls.company.inventory_valuation = "periodic"
        cls.historical_category = cls.categ_basic.copy({"name": "Historical FIFO", "property_cost_method": "fifo"})
        cls.historical_product = cls.create_product("Historical stock product", cls.historical_category, 100, 100)
        cls.source_location = cls.config.picking_type_id.default_location_src_id

    def _movement(self, quantity, stamp, incoming=False, price=100):
        with freeze_time(stamp):
            source = self.env.ref("stock.stock_location_suppliers") if incoming else self.source_location
            destination = self.source_location if incoming else self.env.ref("stock.stock_location_customers")
            vals = {"product_id": self.historical_product.id, "product_uom": self.historical_product.uom_id.id,
                    "product_uom_qty": quantity, "location_id": source.id, "location_dest_id": destination.id,
                    "company_id": self.company.id}
            if incoming:
                vals["value_manual"] = quantity * price
            move = self.env["stock.move"].create(vals)
            move._action_confirm(merge=False)
            move.quantity = quantity
            move.picked = True
            move._action_done()
            return move

    def _target_session(self):
        with freeze_time("2026-01-02 10:00:00"):
            session = self._start_pos_session(self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0)
        with freeze_time("2026-01-02 11:00:00"):
            self._close_session(session)
        self.assertEqual(session.state, "closed")
        return session

    def _source(self, quantity=1, state="cancel"):
        if not self.config.current_session_id:
            self._start_pos_session(self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0)
        return self.env["pos.order"].create({
            "session_id": self.config.current_session_id.id, "state": state,
            "amount_total": 0, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
            "lines": [Command.create({"product_id": self.historical_product.id, "qty": quantity,
                                      "price_unit": 0, "price_subtotal": 0, "price_subtotal_incl": 0})],
        })

    def _prepare(self, source, target):
        action = source.action_prepare_historical_stock()
        picking = self.env["stock.picking"].browse(action["res_id"])
        picking.write({"historical_session_id": target.id, "historical_reason": "Record pre-adoption consumption"})
        return picking

    def _fixture(self, quantity=1, state="cancel"):
        self._movement(5, "2026-01-01 10:00:00", incoming=True)
        target = self._target_session()
        source = self._source(quantity, state)
        return source, self._prepare(source, target), target

    def test_prepare_edit_apply_and_protect_original(self):
        source, picking, target = self._fixture()
        before = source.read(["state", "date_order", "session_id", "amount_total", "lines", "payment_ids"])
        self.assertEqual(picking.state, "draft")
        self.assertFalse(picking.move_ids.move_line_ids)
        self.assertEqual(self.historical_product.qty_available, 5)
        picking.move_ids.product_uom_qty = 2
        before_accounts = self.env["account.move"].search_count([])
        picking.action_apply_historical_stock()
        self.assertEqual(picking.state, "done")
        self.assertEqual(picking.date_done, target.stop_at)
        self.assertEqual(picking.move_ids.date, target.stop_at)
        self.assertEqual(picking.move_ids.move_line_ids.date, target.stop_at)
        self.assertGreater(picking.historical_applied_at, target.stop_at)
        self.assertEqual(picking.move_ids.value, 200)
        self.assertEqual(self.historical_product.qty_available, 3)
        self.assertEqual(self.historical_product.with_context(to_date=target.stop_at).qty_available, 3)
        self.assertEqual(source.read(["state", "date_order", "session_id", "amount_total", "lines", "payment_ids"]), before)
        self.assertEqual(self.env["account.move"].search_count([]), before_accounts)
        self.assertFalse(picking.pos_order_id)
        self.assertFalse(picking.pos_session_id)
        self.assertFalse(picking.move_ids.account_move_id)
        self.assertEqual(source.action_prepare_historical_stock()["res_id"], picking.id)
        picking.action_apply_historical_stock()
        self.assertEqual(self.historical_product.qty_available, 3)

    def test_cancel_draft_and_repeat_preparation(self):
        source, picking, target = self._fixture(state="draft")
        self.assertEqual(source.action_prepare_historical_stock()["res_id"], picking.id)
        picking.action_cancel()
        again = self._prepare(source, target)
        self.assertNotEqual(picking, again)
        self.assertEqual(self.historical_product.qty_available, 5)
        self.assertEqual(source.state, "draft")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            source.write({"state": "paid"})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env["pos.payment"].create({"pos_order_id": source.id, "payment_method_id": self.cash_pm1.id, "amount": 1})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            again.action_confirm()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            again.action_assign()

    def test_invalid_preparation_and_historical_shortage(self):
        source, picking, target = self._fixture()
        for vals in ({"historical_reason": " "}, {"historical_effective_at": fields.Datetime.now() + timedelta(days=1)}, {"historical_effective_at": False}):
            with self.env.cr.savepoint() as sp:
                picking.write(vals)
                with self.assertRaises(UserError):
                    picking.action_apply_historical_stock()
                sp.rollback()
        picking.move_ids.product_uom_qty = 6
        with self.assertRaises(UserError), self.env.cr.savepoint():
            picking.action_apply_historical_stock()
        self.assertEqual(self.historical_product.qty_available, 5)
        picking.move_ids.product_uom_qty = 0
        with self.assertRaises(UserError), self.env.cr.savepoint():
            picking.action_apply_historical_stock()
        picking.move_ids.product_uom_qty = 1
        source.lines.price_unit = 1
        with self.assertRaisesRegex(UserError, "source receipt changed"), self.env.cr.savepoint():
            picking.action_apply_historical_stock()

    def test_reservations_and_later_shortage(self):
        source, picking, target = self._fixture(quantity=2)
        reservation = self.env["stock.move"].create({
            "product_id": self.historical_product.id, "product_uom": self.historical_product.uom_id.id,
            "product_uom_qty": 4, "location_id": self.source_location.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
        })
        reservation._action_confirm(merge=False)
        reservation._action_assign()
        with self.assertRaisesRegex(UserError, "unreserved"), self.env.cr.savepoint():
            picking.action_apply_historical_stock()
        reservation._action_cancel()
        self._movement(5, "2026-01-03 10:00:00")
        self._movement(5, "2026-01-04 10:00:00", incoming=True, price=200)
        with self.assertRaisesRegex(UserError, "shortage"), self.env.cr.savepoint():
            picking.action_apply_historical_stock()
        self.assertEqual(self.historical_product.qty_available, 5)

    def test_complete_rollback_on_stock_failure(self):
        source, picking, target = self._fixture()
        original = type(picking)._action_done
        def fail(records):
            original(records)
            raise UserError("Failure after stock completion")
        with patch.object(type(picking), "_action_done", fail):
            with self.assertRaisesRegex(UserError, "Failure after stock completion"):
                picking.action_apply_historical_stock()
        self.assertEqual(picking.state, "draft")
        self.assertEqual(self.historical_product.qty_available, 5)
        self.assertFalse(picking.historical_applied_at)
        self.assertFalse(picking.move_ids.move_line_ids)

    def test_permissions_and_completed_integrity(self):
        source, picking, target = self._fixture()
        user = new_test_user(self.env, login="historical-denied", groups="point_of_sale.group_pos_manager,stock.group_stock_manager")
        for action in (lambda: source.with_user(user).action_prepare_historical_stock(),
                       lambda: picking.with_user(user).write({"historical_reason": "Forged"}),
                       lambda: picking.with_user(user).action_apply_historical_stock()):
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                action()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            picking.with_context(pos_historical_stock_internal=True).historical_applied_at = fields.Datetime.now()
        picking.action_apply_historical_stock()
        for action in (picking.action_cancel, picking.unlink, picking.copy, picking.move_ids.copy,
                       lambda: picking.move_ids.write({"date": fields.Datetime.now()}),
                       lambda: picking.move_ids.move_line_ids.write({"quantity": 2}),
                       lambda: source.write({"state": "draft"})):
            with self.assertRaises(UserError), self.env.cr.savepoint():
                action()

    def test_manual_recompute_updates_later_nonzero_stock_then_pos(self):
        self._movement(3, "2026-01-01 10:00:00", incoming=True, price=100)
        target = self._target_session()
        self._movement(3, "2026-01-03 10:00:00", incoming=True, price=200)
        with freeze_time("2026-01-04 10:00:00"):
            self.session = self._start_pos_session(self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0)
            later = self._create_orders([{
                "pos_order_lines_ui_args": [(self.historical_product, 3)],
                "payments": [(self.cash_pm1, 300)], "customer": self.customer,
                "uuid": "historical-later-sale",
            }])["historical-later-sale"]
            self._close_session(self.session)
        self.assertEqual(later.lines.total_cost, 300)
        source = self._source(2)
        picking = self._prepare(source, target)
        picking.action_apply_historical_stock()
        self.assertEqual(picking.move_ids.value, 200)
        self.assertEqual(later.lines.total_cost, 300)
        before = later.read(["amount_total", "payment_ids", "state"])
        operation = self.env["pos.cost.recompute"].browse(source.action_prepare_cost_recompute()["res_id"])
        operation.reason = "Recompute from first historical consumption"
        operation.action_preview()
        later_detail = operation.stock_line_ids.filtered(lambda line: line.move_id in later.picking_ids.move_ids)
        self.assertEqual(later_detail.old_value, 300)
        self.assertEqual(later_detail.new_value, 500)
        self.assertEqual(operation.line_ids.new_cost, 500)
        operation.action_apply()
        self.assertEqual(later.picking_ids.move_ids.value, 500)
        self.assertEqual(later.lines.total_cost, 500)
        self.assertEqual(later.read(["amount_total", "payment_ids", "state"]), before)
        self.assertEqual(self.historical_product.qty_available, 1)
        operation.action_apply()
        self.assertEqual(self.historical_product.qty_available, 1)
        self.assertEqual(operation.state, "done")

    def test_recompute_without_pos_and_stale_preview(self):
        source, picking, target = self._fixture()
        picking.action_apply_historical_stock()
        operation = self.env["pos.cost.recompute"].browse(picking.action_prepare_historical_recompute()["res_id"])
        operation.reason = "Stock only"
        operation.action_preview()
        self.assertTrue(operation.can_apply)
        self.assertFalse(operation.line_ids)
        self._movement(1, "2026-01-03 10:00:00", incoming=True, price=200)
        with self.assertRaisesRegex(UserError, "stale"), self.env.cr.savepoint():
            operation.action_apply()
        operation.action_preview()
        operation.action_apply()
        self.assertEqual(operation.state, "done")

    def test_views_preserve_standard_order_list(self):
        for model in ("pos.order", "pos.session", "stock.picking", "pos.cost.recompute"):
            arch = etree.fromstring(self.env[model].get_view(view_type="form")["arch"])
            self.assertEqual(arch.tag, "form")
        view = self.env["pos.order"].get_view(view_type="list")
        names = set(etree.fromstring(view["arch"]).xpath("//field/@name"))
        self.assertTrue({"pos_reference", "partner_id", "amount_total", "state"} <= names)

    def test_two_transfers_and_repeated_manual_recomputation(self):
        self._movement(3, "2026-01-01 10:00:00", incoming=True, price=100)
        target = self._target_session()
        self._movement(3, "2026-01-03 10:00:00", incoming=True, price=200)
        later = self._movement(3, "2026-01-04 10:00:00")
        source = self._source(1)
        first = self._prepare(source, target)
        first.action_apply_historical_stock()
        operation = self.env["pos.cost.recompute"].browse(first.action_prepare_historical_recompute()["res_id"])
        operation.reason = "First manual recomputation"
        operation.action_preview()
        operation.action_apply()
        self.assertEqual(later.value, 400)
        first_evidence = operation.stock_line_ids.read(["old_value", "new_value", "actual_value"])
        second_source = self._source(1)
        second = self._prepare(second_source, target)
        second.action_apply_historical_stock()
        self.assertEqual(later.value, 400)
        next_operation = self.env["pos.cost.recompute"].browse((first | second).action_prepare_historical_recompute()["res_id"])
        next_operation.reason = "Second manual recomputation"
        next_operation.action_preview()
        next_operation.action_apply()
        self.assertEqual(later.value, 500)
        self.assertEqual(self.historical_product.qty_available, 1)
        self.assertEqual(operation.stock_line_ids.read(["old_value", "new_value", "actual_value"]), first_evidence)
        action = source.action_view_cost_recomputations()
        self.assertIn(next_operation, self.env["pos.cost.recompute"].search(action["domain"]))

    def test_duplicate_products_keep_both_requested_lines(self):
        source, picking, target = self._fixture()
        self.env["stock.move"].create({
            "picking_id": picking.id, "product_id": self.historical_product.id,
            "product_uom": self.historical_product.uom_id.id, "product_uom_qty": 2,
            "location_id": self.source_location.id, "location_dest_id": picking.location_dest_id.id,
        })
        picking.action_apply_historical_stock()
        self.assertEqual(len(picking.move_ids), 2)
        self.assertEqual(sum(picking.move_ids.mapped("quantity")), 3)
        self.assertEqual(sum(picking.move_ids.mapped("value")), 300)
        self.assertEqual(self.historical_product.qty_available, 2)

    def test_wrong_pos_company_and_unsupported_valuation(self):
        source, picking, target = self._fixture()
        another_config = self.config.copy({"name": "Other historical POS"})
        with self.env.cr.savepoint() as sp:
            target.config_id = another_config
            with self.assertRaisesRegex(UserError, "same company and POS"):
                picking.action_apply_historical_stock()
            sp.rollback()
        another_company = self.env["res.company"].create({"name": "Historical unauthorized company"})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            picking.with_context(allowed_company_ids=another_company.ids).action_apply_historical_stock()
        self.historical_category.property_cost_method = "average"
        with self.assertRaisesRegex(UserError, "FIFO and periodic"), self.env.cr.savepoint():
            picking.action_apply_historical_stock()
        self.assertEqual(picking.state, "draft")
        self.assertEqual(self.historical_product.qty_available, 5)

    def test_overlapping_source_and_direct_delivery_are_rejected(self):
        source, picking, target = self._fixture()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            source._create_order_picking()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env["stock.picking"].create({
                "picking_type_id": picking.picking_type_id.id,
                "location_id": picking.location_id.id, "location_dest_id": picking.location_dest_id.id,
                "pos_order_id": source.id,
            })
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env["pos.order.line"].create({
                "order_id": source.id, "refunded_orderline_id": source.lines.id,
                "product_id": self.historical_product.id, "qty": -1, "price_unit": 0,
                "price_subtotal": 0, "price_subtotal_incl": 0,
            })
        picking.action_cancel()
        paid = self._create_paid_order("historical-reject-paid")
        with self.assertRaisesRegex(UserError, "draft or cancelled"), self.env.cr.savepoint():
            paid.action_prepare_historical_stock()

    def test_manual_recompute_failure_rolls_back_stock_values(self):
        self._movement(3, "2026-01-01 10:00:00", incoming=True)
        target = self._target_session()
        self._movement(3, "2026-01-03 10:00:00", incoming=True, price=200)
        later = self._movement(3, "2026-01-04 10:00:00")
        source = self._source(1)
        picking = self._prepare(source, target)
        picking.action_apply_historical_stock()
        operation = self.env["pos.cost.recompute"].browse(picking.action_prepare_historical_recompute()["res_id"])
        operation.reason = "Rollback proof"
        operation.action_preview()
        original = type(operation)._apply_stock_plan
        def fail(record):
            original(record)
            self.assertEqual(later.value, 400)
            raise UserError("Failure after stock revaluation")
        with patch.object(type(operation), "_apply_stock_plan", fail):
            with self.assertRaisesRegex(UserError, "Failure after stock revaluation"):
                operation.action_apply()
        self.assertEqual(operation.state, "ready")
        self.assertEqual(later.value, 300)
        self.assertFalse(later.historical_cost_line_id)
        self.assertEqual(self.historical_product.qty_available, 2)

    def test_draft_deletion_and_uninstallation_protection(self):
        source, picking, target = self._fixture()
        picking.unlink()
        self.assertFalse(source.historical_picking_ids)
        picking = self._prepare(source, target)
        picking.action_apply_historical_stock()
        module = self.env['ir.module.module'].search([('name', '=', 'pos_historical_stock_writeoff')])
        with self.assertRaisesRegex(UserError, 'cannot be removed'), self.env.cr.savepoint():
            module.write({'state': 'to remove'})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            source.partner_id = self.partner_a

    def test_period_lock_and_missing_tracking(self):
        source, picking, target = self._fixture()
        with self.env.cr.savepoint() as sp:
            self.company.sudo().fiscalyear_lock_date = fields.Date.to_date('2026-01-02')
            with self.assertRaisesRegex(UserError, 'locked or closed'):
                picking.action_apply_historical_stock()
            sp.rollback()
        picking.historical_effective_at = fields.Datetime.to_datetime('2026-01-02 10:30:00')
        self.historical_product.tracking = 'lot'
        with self.assertRaisesRegex(UserError, 'lot or serial'):
            picking.action_apply_historical_stock()
        self.assertEqual(picking.state, 'draft')
        self.assertEqual(self.historical_product.qty_available, 5)

    def test_historical_recomputation_permissions_and_audited_move_lines(self):
        source, picking, target = self._fixture()
        later = self._movement(1, '2026-01-03 10:00:00')
        picking.action_apply_historical_stock()
        operation = self.env['pos.cost.recompute'].browse(picking.action_prepare_historical_recompute()['res_id'])
        operation.reason = 'Protect reviewed values'
        unauthorized = new_test_user(self.env, login='historical_cost_without_permission',
                                     groups='point_of_sale.group_pos_manager,stock.group_stock_manager',
                                     company_id=self.company.id, company_ids=[Command.set(self.company.ids)])
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            operation.with_user(unauthorized).action_preview()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env['pos.cost.recompute'].with_user(unauthorized).create({
                'selection_type': 'historical', 'historical_picking_ids': [Command.set(picking.ids)],
                'company_id': self.company.id,
            })
        operation.action_preview()
        operation.action_apply()
        self.assertTrue(later.historical_cost_line_id)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            later.move_line_ids.quantity = 2
        with self.assertRaises(UserError), self.env.cr.savepoint():
            later.move_line_ids.unlink()
        self.assertEqual(later.quantity, 1)
        self.assertEqual(picking.with_user(unauthorized).read(['state'])[0]['state'], 'done')

    def test_ordinary_stock_user_without_pos_rights(self):
        stock_user = new_test_user(self.env, login='ordinary_stock_without_pos', groups='stock.group_stock_user',
                                   company_id=self.company.id, company_ids=[Command.set(self.company.ids)])
        picking = self.env['stock.picking'].with_user(stock_user).create({
            'picking_type_id': self.config.picking_type_id.id,
            'location_id': self.source_location.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
        })
        self.assertFalse(picking.historical_pos_order_id)
        picking.unlink()

    def test_units_and_empty_preparation(self):
        source, picking, target = self._fixture()
        with self.env.cr.savepoint() as sp:
            picking.move_ids.unlink()
            with self.assertRaisesRegex(UserError, 'at least one stock line'):
                picking.action_apply_historical_stock()
            sp.rollback()
        dozen = self.env.ref('uom.product_uom_dozen')
        picking.move_ids.product_uom = dozen
        with self.assertRaisesRegex(UserError, 'positive stock quantities'):
            picking.action_apply_historical_stock()
        self.historical_product.uom_ids = [Command.link(dozen.id)]
        picking.move_ids.product_uom_qty = 0.25
        picking.action_apply_historical_stock()
        self.assertEqual(picking.move_ids._get_valued_qty(), 3)
        self.assertEqual(picking.move_ids.value, 300)
        self.assertEqual(self.historical_product.qty_available, 2)
        self.assertEqual(source.lines.qty, 1)

    def test_reject_current_stock_without_historical_receipt(self):
        target = self._target_session()
        self._movement(5, '2026-01-03 10:00:00', incoming=True)
        source = self._source(1)
        picking = self._prepare(source, target)
        with self.assertRaisesRegex(UserError, 'Insufficient historical stock'):
            picking.action_apply_historical_stock()
        self.assertEqual(picking.state, 'draft')
        self.assertFalse(picking.move_ids.move_line_ids)
        self.assertEqual(self.historical_product.qty_available, 5)

    def test_reject_unsupported_subsequent_pos_before_consumption(self):
        self._movement(5, '2026-01-01 10:00:00', incoming=True)
        target = self._target_session()
        with freeze_time('2026-01-04 10:00:00'):
            self.session = self._start_pos_session(self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0)
            later = self._create_orders([{
                'pos_order_lines_ui_args': [(self.historical_product, 1)],
                'payments': [(self.cash_pm1, 100)], 'customer': self.customer,
                'uuid': 'historical-open-session-sale',
            }])['historical-open-session-sale']
        self.assertTrue(later.picking_ids)
        source = self._source(1)
        picking = self._prepare(source, target)
        with self.assertRaisesRegex(UserError, 'session is not closed'):
            picking.action_apply_historical_stock()
        self.assertEqual(picking.state, 'draft')
        self.assertEqual(self.historical_product.qty_available, 4)

    def test_edit_historical_preparation_through_standard_form(self):
        source, picking, target = self._fixture()
        replacement = self.create_product("Edited historical product", self.historical_category, 100, 100)
        planned = target.start_at - timedelta(days=1)
        with Form(picking) as form:
            form.historical_reason = "Edited through the standard stock form"
            with form.move_ids.edit(0) as line:
                line.product_uom_qty = 2
        self.assertEqual(picking.move_ids.product_uom_qty, 2)
        with Form(picking) as form:
            form.scheduled_date = planned
        self.assertEqual(picking.move_ids.date, planned)
        with Form(picking) as form:
            with form.move_ids.edit(0) as line:
                line.product_id = replacement
        self.assertEqual(picking.move_ids.product_id, replacement)
        with Form(picking) as form:
            with form.move_ids.edit(0) as line:
                line.product_id = self.historical_product
            form.historical_effective_at = target.start_at + timedelta(minutes=15)
        self.assertEqual(picking.state, "draft")
        self.assertFalse(picking.move_ids.move_line_ids)
        self.assertEqual(source.lines.product_id, self.historical_product)
        self.assertEqual(source.lines.qty, 1)
        self.assertEqual(self.historical_product.qty_available, 5)
        picking.action_apply_historical_stock()
        self.assertEqual(picking.date_done, picking.historical_effective_at)
        self.assertEqual(picking.move_ids.date, picking.historical_effective_at)
        self.assertEqual(picking.move_ids.move_line_ids.date, picking.historical_effective_at)
        self.assertEqual(picking.move_ids.value, 200)
        self.assertEqual(self.historical_product.qty_available, 3)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            picking.move_ids.date = planned

    def test_independent_stock_time_after_session_and_receipt(self):
        target = self._target_session()
        self._movement(30, "2026-01-02 11:15:00", incoming=True)
        source = self._source(14)
        picking = self._prepare(source, target)
        before = target.read(["state", "start_at", "stop_at", "move_id"])
        with self.assertRaisesRegex(UserError, "Insufficient historical stock"):
            picking.action_apply_historical_stock()
        stamp = fields.Datetime.to_datetime("2026-01-02 11:30:00")
        with Form(picking) as form:
            form.historical_effective_at = stamp
        picking.action_apply_historical_stock()
        self.assertEqual(picking.date_done, stamp)
        self.assertEqual(picking.move_ids.date, stamp)
        self.assertEqual(picking.move_ids.move_line_ids.date, stamp)
        self.assertEqual(picking.move_ids.value, 1400)
        self.assertEqual(self.historical_product.qty_available, 16)
        self.assertEqual(target.read(["state", "start_at", "stop_at", "move_id"]), before)
        self.assertEqual(source.state, "cancel")
        self.assertFalse(source.payment_ids)
        operation = self.env["pos.cost.recompute"].browse(picking.action_prepare_historical_recompute()["res_id"])
        operation.action_preview()
        self.assertEqual(operation.stock_line_ids.move_id, picking.move_ids)

    def test_independent_stock_time_before_session_and_preserved_on_selection(self):
        self._movement(5, "2026-01-01 10:00:00", incoming=True)
        target = self._target_session()
        source = self._source()
        picking = self.env["stock.picking"].browse(source.action_prepare_historical_stock()["res_id"])
        stamp = fields.Datetime.to_datetime("2026-01-01 11:00:00")
        picking.historical_effective_at = stamp
        with Form(picking) as form:
            form.historical_session_id = target
            form.historical_reason = "Service consumption before the linked session"
        self.assertEqual(picking.historical_effective_at, stamp)
        picking.write({"historical_session_id": target.id})
        self.assertEqual(picking.historical_effective_at, stamp)
        picking.action_apply_historical_stock()
        self.assertEqual(picking.move_ids.date, stamp)
        self.assertEqual(picking.historical_session_id, target)
        self.assertEqual(self.historical_product.qty_available, 4)
