from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.pos_cost_recompute.models.source_revision import _touch

from .history import check_permission


class ProductConsolidationService(models.AbstractModel):
    _inherit = "product.card.consolidation.service"

    @api.model
    def _history_extra_blockers(self, canonical, sources, records):
        blockers = super()._history_extra_blockers(canonical, sources, records)
        try:
            sources.filtered(lambda source: source.active and not source.merged_into_id)._ensure_unused_in_pos()
        except UserError as error:
            blockers.append(self._line("blocker", "active_pos", 1, str(error)))
        return blockers

    @api.model
    def _history_extra_warnings(self, real):
        warnings = super()._history_extra_warnings(real)
        locations = real.location_id.filtered(lambda location: location.usage == "internal") | real.location_dest_id.filtered(lambda location: location.usage == "internal")
        unsupported = (len(locations) > 1 or real.filtered("origin_returned_move_id")
                       or real.move_line_ids.filtered(lambda line: line.package_id or line.result_package_id)
                       or real.filtered(lambda move: not (
                           move.location_id.usage == "supplier" and move.location_dest_id.usage == "internal"
                           or move.location_id.usage == "internal" and move.location_dest_id.usage == "customer")))
        if unsupported:
            warnings.append(self._line("warning", "recompute_profile", len(real), _(
                "History can be consolidated, but historical write-offs and cost recomputation require direct supplier receipts and customer issues in one unpackaged stock location. This history requires separate review."
            )))
        return warnings

    @api.model
    def _history_after_rewrite(self, canonical, plan):
        super()._history_after_rewrite(canonical, plan)
        _touch(plan["products"])
        _touch(plan["records"].get("pos.order.line", self.env["pos.order.line"]).order_id)


class ProductConsolidationOperation(models.Model):
    _inherit = "product.consolidation.operation"

    def action_recompute_costs(self):
        self.ensure_one()
        self.check_access("read")
        check_permission(self.env)
        self.env["pos.cost.recompute"]._check_manager()
        if not self.canonical_id._has_full_consolidation_history(self.company_id):
            raise UserError(_("Convert every remaining source before recomputing the unified history."))
        return {
            "type": "ir.actions.act_window", "name": _("Recompute Consolidated History Costs"),
            "res_model": "pos.cost.recompute", "view_mode": "form", "target": "current",
            "context": {"default_selection_type": "consolidation", "default_company_id": self.company_id.id,
                        "default_consolidation_operation_ids": self.ids, "default_cost_mode": "all"},
        }
