from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

from .utils import CORRECTION_INTERNAL_TOKEN, is_internal_correction_call


class StockMove(models.Model):
    _inherit = "stock.move"

    def _correction_roots(self):
        # Stock operators may process a POS delivery without access to the POS
        # application. Resolve only its integrity links, never elevate the move.
        orders = self.sudo().reference_ids.pos_order_ids | self.sudo().picking_id.pos_order_id
        roots = orders.mapped(lambda order: order._get_correction_root())
        return roots.filtered("correction_ids")

    def _protected_correction_moves(self):
        return self.filtered(lambda move: move._correction_roots().correction_ids.filtered(
            lambda correction: correction.state == "applied"
        ))

    @api.model_create_multi
    def create(self, vals_list):
        if not is_internal_correction_call(self.env):
            origins = self.browse([
                values.get("origin_returned_move_id", self.env.context.get("default_origin_returned_move_id"))
                for values in vals_list
                if values.get("origin_returned_move_id", self.env.context.get("default_origin_returned_move_id"))
            ])
            if origins._protected_correction_moves():
                raise UserError(self.env._("Return corrected deliveries through the source POS order."))
        with self.env.cr.savepoint():
            moves = super().create(vals_list)
            if not is_internal_correction_call(self.env) and moves._protected_correction_moves():
                raise UserError(self.env._("Correction stock effects cannot be added independently."))
            return moves

    def write(self, vals):
        if not is_internal_correction_call(self.env):
            self._correction_roots()._lock_correction_chain()
            protected = self._protected_correction_moves()
            identity = {
                "product_id", "product_uom", "product_uom_qty", "location_id",
                "location_dest_id", "company_id", "picking_id", "reference_ids",
                "origin_returned_move_id", "state", "date", "price_unit",
                "never_product_template_attribute_value_ids",
            }
            if protected and identity.intersection(vals):
                raise UserError(self.env._("Correction stock effects cannot be edited independently."))
            if protected.filtered(lambda move: move.state == "done") and {
                "quantity", "move_line_ids", "lot_ids", "picked",
            }.intersection(vals):
                raise UserError(self.env._("Completed correction quantities cannot be edited."))
            if "quantity" in vals:
                for move in protected:
                    if vals["quantity"] < 0 or float_compare(
                        vals["quantity"], move.product_uom_qty,
                        precision_rounding=move.product_uom.rounding,
                    ) > 0:
                        raise UserError(self.env._("The delivered quantity exceeds the corrected demand."))
        if not is_internal_correction_call(self.env) and {"reference_ids", "picking_id"}.intersection(vals):
            with self.env.cr.savepoint():
                result = super().write(vals)
                if self._protected_correction_moves():
                    raise UserError(self.env._("Correction stock source links cannot be assigned independently."))
                return result
        return super().write(vals)

    def unlink(self):
        if self._protected_correction_moves() and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction stock effects cannot be deleted."))
        return super().unlink()

    def copy_data(self, default=None):
        if self._protected_correction_moves() and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction stock effects cannot be copied."))
        return super().copy_data(default)

    def _action_cancel(self):
        if self._protected_correction_moves() and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction demand can only be cancelled by another correction."))
        return super()._action_cancel()

    def _action_assign(self, force_qty=False):
        if not self._correction_roots():
            return super()._action_assign(force_qty=force_qty)
        self.check_access("write")
        self._correction_roots()._lock_correction_chain()
        return super(StockMove, self.with_context(
            pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN
        ))._action_assign(force_qty=force_qty)

    def _action_done(self, cancel_backorder=False):
        roots = self._correction_roots()
        if not roots:
            return super()._action_done(cancel_backorder=cancel_backorder)
        self.check_access("write")
        roots._lock_correction_chain()
        for move in self._protected_correction_moves():
            if float_compare(move.quantity, move.product_uom_qty,
                             precision_rounding=move.product_uom.rounding) > 0:
                raise UserError(self.env._("The delivered quantity exceeds the corrected demand."))
        if cancel_backorder and self._protected_correction_moves().filtered(
            lambda move: float_compare(move.quantity, move.product_uom_qty,
                                       precision_rounding=move.product_uom.rounding) < 0
        ):
            raise UserError(self.env._("Keep the remaining corrected demand as a backorder."))
        return super(StockMove, self.with_context(
            pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN
        ))._action_done(cancel_backorder=cancel_backorder)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def write(self, vals):
        if not is_internal_correction_call(self.env):
            moves = self.move_id | self.env["stock.move"].browse(vals.get("move_id", []))
            moves._correction_roots()._lock_correction_chain()
            protected = moves._protected_correction_moves()
            if protected and ({"move_id", "product_id", "product_uom_id", "location_id",
                               "location_dest_id", "company_id", "picking_id", "lot_id", "lot_name"}.intersection(vals)
                              or protected.filtered(lambda move: move.state == "done") and
                              {"quantity", "lot_id", "lot_name", "date", "picked"}.intersection(vals)):
                raise UserError(self.env._("Correction stock details cannot be edited independently."))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if not is_internal_correction_call(self.env):
            moves = self.env["stock.move"].browse([
                values.get("move_id", self.env.context.get("default_move_id"))
                for values in vals_list if values.get("move_id", self.env.context.get("default_move_id"))
            ])
            if moves._protected_correction_moves().filtered(lambda move: move.state == "done"):
                raise UserError(self.env._("Completed correction stock details cannot be extended."))
        return super().create(vals_list)

    def unlink(self):
        if self.move_id._protected_correction_moves() and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction stock details cannot be deleted independently."))
        return super().unlink()


class StockReference(models.Model):
    _inherit = "stock.reference"

    def _has_correction_history(self):
        orders = self.sudo().pos_order_ids
        return any(order.is_correction_order or order.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        ) for order in orders)

    def write(self, vals):
        if {"pos_order_ids", "move_ids"}.intersection(vals) and self._has_correction_history() and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction stock source links cannot be edited."))
        return super().write(vals)

    def unlink(self):
        if self._has_correction_history():
            raise UserError(self.env._("Correction stock source links cannot be deleted."))
        return super().unlink()


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _has_correction_history(self):
        orders = self.sudo().pos_order_id
        return self.move_ids._protected_correction_moves() or any(
            order.is_correction_order or order.correction_ids.filtered(
                lambda correction: correction.state == "applied"
            ) for order in orders
        )

    @api.model_create_multi
    def create(self, vals_list):
        with self.env.cr.savepoint():
            pickings = super().create(vals_list)
            if not is_internal_correction_call(self.env) and pickings._has_correction_history():
                raise UserError(self.env._("Correction deliveries cannot be assigned independently."))
            return pickings

    def write(self, vals):
        if not is_internal_correction_call(self.env) and self.move_ids._protected_correction_moves() and {
            "move_ids", "move_line_ids", "location_id", "location_dest_id", "company_id",
            "pos_order_id", "pos_session_id", "state", "date_done",
        }.intersection(vals):
            raise UserError(self.env._("Correction deliveries cannot be edited independently."))
        if not is_internal_correction_call(self.env) and "pos_order_id" in vals:
            with self.env.cr.savepoint():
                result = super().write(vals)
                if self._has_correction_history():
                    raise UserError(self.env._("Correction deliveries cannot be assigned independently."))
                return result
        return super().write(vals)

    def copy_data(self, default=None):
        if self.move_ids._protected_correction_moves() and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction deliveries cannot be copied."))
        return super().copy_data(default)

    def unlink(self):
        if self.move_ids._protected_correction_moves():
            raise UserError(self.env._("Correction deliveries cannot be deleted."))
        return super().unlink()

    def button_validate(self):
        protected = self.move_ids._protected_correction_moves()
        if not protected:
            return super().button_validate()
        self.check_access("write")
        protected._correction_roots()._lock_correction_chain()
        return super(StockPicking, self.with_context(
            pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN
        )).button_validate()


class AccountMove(models.Model):
    _inherit = "account.move"

    def _protected_correction_entries(self):
        def is_protected(move):
            if move.move_type != "entry":
                return False
            # Check integrity ownership without changing accounting permissions.
            source = move.sudo()
            orders = source.pos_session_ids.order_ids | source.pos_payment_ids.pos_order_id | source.reversed_pos_order_id
            return any(order.is_correction_order or order.correction_ids.filtered(
                lambda correction: correction.state == "applied"
            ) for order in orders)
        return self.filtered(is_protected)

    def write(self, vals):
        if not is_internal_correction_call(self.env) and self._protected_correction_entries() and {
            "state", "date", "journal_id", "company_id", "currency_id", "line_ids",
            "pos_session_ids", "pos_payment_ids", "reversed_pos_order_id",
        }.intersection(vals):
            raise UserError(self.env._("Correction accounting entries cannot be edited independently."))
        return super().write(vals)

    def button_draft(self):
        if self._protected_correction_entries() and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction accounting entries cannot be reset to draft."))
        return super().button_draft()

    def unlink(self):
        if self._protected_correction_entries() and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction accounting entries cannot be deleted."))
        return super().unlink()

    def copy_data(self, default=None):
        if self._protected_correction_entries() and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction accounting entries cannot be copied."))
        return super().copy_data(default)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _lock_debt_correction_roots(self, payment_id=False):
        # Follow the same root-first lock order as partial reconciliation.
        # Resolve only ownership with sudo; journal-item permissions are kept.
        payments = self.sudo().pos_debt_payment_id | self.env["pos.payment"].sudo().browse(
            payment_id or []
        )
        roots = payments.pos_order_id.mapped(lambda order: order._get_correction_root())
        roots.filtered("correction_ids")._lock_correction_chain()

    @api.model_create_multi
    def create(self, vals_list):
        if not is_internal_correction_call(self.env):
            moves = self.env["account.move"].browse([
                values.get("move_id", self.env.context.get("default_move_id"))
                for values in vals_list if values.get("move_id", self.env.context.get("default_move_id"))
            ])
            if moves._protected_correction_entries():
                raise UserError(self.env._("Correction journal items cannot be added independently."))
        return super().create(vals_list)

    def write(self, vals):
        if not is_internal_correction_call(self.env):
            self._lock_debt_correction_roots(vals.get("pos_debt_payment_id"))
            moves = self.move_id | self.env["account.move"].browse(vals.get("move_id", []))
            if moves._protected_correction_entries() and {
                "move_id", "account_id", "debit", "credit", "balance", "amount_currency",
                "currency_id", "partner_id", "product_id", "quantity", "price_unit",
                "tax_ids", "tax_line_id", "company_id", "pos_debt_payment_id",
            }.intersection(vals):
                raise UserError(self.env._("Correction journal items cannot be edited independently."))
        return super().write(vals)

    def unlink(self):
        if not is_internal_correction_call(self.env):
            self._lock_debt_correction_roots()
            if self.move_id._protected_correction_entries():
                raise UserError(self.env._("Correction journal items cannot be deleted."))
        return super().unlink()


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    @api.model_create_multi
    def create(self, vals_list):
        roots = self.env["pos.order"]
        if not is_internal_correction_call(self.env):
            lines = self.env["account.move.line"].browse([
                values.get(field, self.env.context.get("default_" + field))
                for values in vals_list for field in ("debit_move_id", "credit_move_id")
                if values.get(field, self.env.context.get("default_" + field))
            ])
            lines.check_access("read")
            # This audit flag describes already authorized journal items. It
            # must also survive an accountant's later removal of the matching.
            orders = lines.sudo().pos_debt_payment_id.pos_order_id
            roots = orders.mapped(lambda order: order._get_correction_root())
            roots._lock_correction_chain()
            if any(root.correction_pending for root in roots):
                raise UserError(self.env._("Close all correction sessions before settling this debt."))
        partials = super().create(vals_list)
        if roots:
            roots.with_context(pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN).write(
                {"correction_has_external_settlement": True}
            )
        return partials

    def write(self, vals):
        if not is_internal_correction_call(self.env) and {
            "debit_move_id", "credit_move_id", "amount", "debit_amount_currency",
            "credit_amount_currency", "debit_currency_id", "credit_currency_id",
        }.intersection(vals) and (
            self.sudo().debit_move_id.pos_debt_payment_id
            or self.sudo().credit_move_id.pos_debt_payment_id
        ):
            raise UserError(self.env._("POS debt matching amounts cannot be edited independently."))
        return super().write(vals)

    def unlink(self):
        if not is_internal_correction_call(self.env) and self.env["pos.order.correction"].sudo().search_count([
            ("state", "=", "applied"), ("internal_partial_reconcile_ids", "in", self.ids),
        ], limit=1):
            raise UserError(self.env._("Internal correction offsets cannot be removed independently."))
        return super().unlink()
