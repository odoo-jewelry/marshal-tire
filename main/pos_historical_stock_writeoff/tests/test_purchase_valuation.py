from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.service.model import get_public_method
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from odoo.addons.pos_order_correction.tests.common import PosOrderCorrectionCommon

from .test_historical_stock import TestHistoricalStock


@tagged("post_install", "-at_install", "historical_purchase_valuation")
class TestHistoricalPurchaseValuation(PosOrderCorrectionCommon):
    _movement = TestHistoricalStock._movement
    _target_session = TestHistoricalStock._target_session
    _source = TestHistoricalStock._source
    _prepare = TestHistoricalStock._prepare
    _fixture = TestHistoricalStock._fixture

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids = [Command.link(cls.env.ref(
            "pos_historical_stock_writeoff.group_historical_stock",
        ).id)]
        cls.company.inventory_valuation = "periodic"
        cls.category = cls.categ_basic.copy({
            "name": "Historical purchase valuation", "property_cost_method": "fifo",
        })
        cls.historical_product = cls.create_product("Historical purchase goods", cls.category, 100, 100)
        cls.source_location = cls.config.picking_type_id.default_location_src_id

    def _completed_writeoff(self, extra_move=False):
        source, picking, _session = self._fixture()
        picking.move_ids.product_uom_qty = 2
        if extra_move:
            self.env["stock.move"].create({
                "product_id": self.historical_product.id,
                "product_uom": self.historical_product.uom_id.id,
                "product_uom_qty": 1,
                "picking_id": picking.id,
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
                "company_id": self.company.id,
            })
        picking.action_apply_historical_stock()
        return source, picking, picking.move_ids.with_context(allowed_company_ids=self.company.ids)

    def test_value_only_preserves_edited_quantity_and_source(self):
        source, picking, moves = self._completed_writeoff()
        facts = ["product_id", "quantity", "product_uom_qty", "date", "state", "location_id",
                 "location_dest_id", "picking_id", "historical_cost_line_id", "cost_repair_line_id"]
        source_fields = ["state", "date_order", "session_id", "amount_total", "payment_ids", "lines"]
        picking_fields = ["state", "historical_source_snapshot", "historical_applied_at", "date_done",
                          "historical_session_id", "historical_pos_order_id", "historical_reason"]
        before_moves = moves.read(facts)
        before_source = source.read(source_fields)
        before_lines = source.lines.read(["product_id", "qty", "price_unit", "total_cost"])
        before_picking = picking.read(picking_fields)
        before_quantity = self.historical_product.qty_available
        journals = self.env["pos.cost.recompute"].search_count([])
        self.assertEqual(source.lines.qty, 1)
        self.assertEqual(moves.quantity, 2)
        moves._check_historical_purchase_valuation()
        moves._write_historical_purchase_values({moves.id: 240})
        self.assertEqual(moves.value, 240)
        self.assertEqual(moves.read(facts), before_moves)
        self.assertEqual(source.read(source_fields), before_source)
        self.assertEqual(source.lines.read(["product_id", "qty", "price_unit", "total_cost"]), before_lines)
        self.assertEqual(picking.read(picking_fields), before_picking)
        self.assertEqual(self.historical_product.qty_available, before_quantity)
        self.assertEqual(self.env["pos.cost.recompute"].search_count([]), journals)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            moves.write({"value": 250})

    def test_exact_batch_and_all_values_are_validated_before_writing(self):
        _source, _picking, moves = self._completed_writeoff(extra_move=True)
        self.assertEqual(len(moves), 2)
        before = moves.mapped("value")
        valid = {move.id: 120 * move.quantity for move in moves}
        invalid = [None, {}, {moves[0].id: 120}, dict(valid, unrelated=120)]
        invalid.extend(dict(valid, **{str(moves[-1].id): value}) for value in (0, -1))
        for value in (0, -1, float("nan"), float("inf"), True, "120", {"value": 120}):
            values = dict(valid)
            values[moves[-1].id] = value
            invalid.append(values)
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(UserError), self.env.cr.savepoint():
                moves._write_historical_purchase_values(values)
            self.assertEqual(moves.mapped("value"), before)
        moves._write_historical_purchase_values(valid)
        self.assertEqual(moves.mapped("value"), [valid[move.id] for move in moves])

    def test_permission_and_hidden_source_are_checked(self):
        source, _picking, moves = self._completed_writeoff()
        denied = new_test_user(self.env, login="historical-purchase-denied",
                               groups="stock.group_stock_manager,point_of_sale.group_pos_manager")
        allowed = new_test_user(self.env, login="historical-purchase-allowed",
                                groups="pos_historical_stock_writeoff.group_historical_stock")
        for user in (denied, allowed):
            user.write({"company_id": self.company.id, "company_ids": [Command.set(self.company.ids)]})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            moves.with_user(denied)._write_historical_purchase_values({moves.id: 240})
        moves.with_user(allowed)._check_historical_purchase_valuation()
        self.env["ir.rule"].create({
            "name": "Hide historical preparation source",
            "model_id": self.env["ir.model"]._get_id("pos.order"),
            "domain_force": repr([("id", "!=", source.id)]),
        })
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            moves.with_user(allowed)._write_historical_purchase_values({moves.id: 240})
        self.assertEqual(moves.value, 200)

    def test_company_scope_and_nonhistorical_moves_are_rejected(self):
        _source, _picking, moves = self._completed_writeoff()
        other_company = self.env["res.company"].create({"name": "Other historical purchase company"})
        for companies in (other_company, self.company | other_company):
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                moves.with_context(allowed_company_ids=companies.ids)._write_historical_purchase_values({moves.id: 240})
        ordinary = self._movement(1, "2026-01-03 10:00:00")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            ordinary._write_historical_purchase_values({ordinary.id: 120})
        self.assertEqual(moves.value, 200)

    def test_private_entry_points_and_forged_context_do_not_bypass_protection(self):
        _source, _picking, moves = self._completed_writeoff()
        for name in ("_check_historical_purchase_valuation", "_write_historical_purchase_values"):
            with self.assertRaises(AccessError):
                get_public_method(moves, name)
        for context in ({"pos_historical_stock_valuation": True},
                        {"pos_historical_stock_internal": True},
                        {"pos_historical_stock_valuation": "_VALUATION"}):
            for values in ({"value": 240}, {"quantity": 3}, {"value": 240, "quantity": 3}):
                with self.subTest(context=context, values=values), self.assertRaises(UserError), self.env.cr.savepoint():
                    moves.with_context(context).write(values)
        moves._write_historical_purchase_values({moves.id: 240})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            moves.write({"quantity": 3})

    def test_previous_reviewed_valuation_remains_protected(self):
        _source, picking, moves = self._completed_writeoff()
        operation = self.env["pos.cost.recompute"].browse(picking.action_prepare_historical_recompute()["res_id"])
        operation.reason = "Review the original historical valuation"
        operation.action_preview()
        operation.action_apply()
        self.assertTrue(moves.historical_cost_line_id)
        with self.assertRaisesRegex(UserError, "protected previous cost correction"), self.env.cr.savepoint():
            moves._write_historical_purchase_values({moves.id: 240})
        self.assertEqual(moves.value, 200)

    def test_existing_history_survives_disabled_inventory_tracking(self):
        _source, _picking, moves = self._completed_writeoff()
        self.historical_product.is_storable = False
        moves._write_historical_purchase_values({moves.id: 240})
        self.assertFalse(self.historical_product.is_storable)
        self.assertEqual(moves.value, 240)
