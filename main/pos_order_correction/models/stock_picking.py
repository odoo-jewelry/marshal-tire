from odoo import Command, api, models
from odoo.exceptions import UserError

from .utils import CORRECTION_INTERNAL_TOKEN


_STOCK_CONTEXT_TOKEN = object()


def _stock_context(**values):
    # A JSON/RPC caller cannot manufacture the identity token inside this value.
    return {"pos_order_correction_stock_context": (_STOCK_CONTEXT_TOKEN, values)}


def _stock_context_values(env):
    value = env.context.get("pos_order_correction_stock_context")
    if isinstance(value, tuple) and len(value) == 2 and value[0] is _STOCK_CONTEXT_TOKEN:
        return value[1]
    return {}


class StockPicking(models.Model):
    _inherit = "stock.picking"

    @api.model
    def _correction_stock_ancestors(self, line):
        ancestors = self.env["pos.order.line"]
        while line and line not in ancestors:
            ancestors |= line
            line = line.correction_origin_line_id
        return ancestors

    @api.model
    def _correction_stock_identity(self, line):
        attributes = line.attribute_value_ids.filtered(
            lambda value: value.attribute_id.create_variant == "no_variant"
        )
        return line.product_id, attributes

    @api.model
    def _correction_matching_moves(self, line):
        ancestors = self._correction_stock_ancestors(line)
        orders = ancestors.order_id
        product, attributes = self._correction_stock_identity(line)
        return (orders.picking_ids.move_ids | orders.stock_reference_ids.move_ids).filtered(
            lambda move: move.product_id == product
            and move.never_product_template_attribute_value_ids == attributes
            and move.location_dest_id.usage == "customer"
            and move.state != "cancel"
        )

    @api.model
    def _check_correction_stock_sources(self, lines):
        groups = {}
        for line in lines.filtered(lambda item: item.product_id.type == "consu"):
            product, attributes = self._correction_stock_identity(line)
            key = (product.id, tuple(sorted(attributes.ids)))
            group = groups.setdefault(key, {
                "lines": self.env["pos.order.line"],
                "moves": self.env["stock.move"],
                "deferred": self.env["pos.order.line"],
            })
            group["lines"] |= line
            group["moves"] |= self._correction_matching_moves(line)
            for source in self._correction_stock_ancestors(line):
                if self._correction_stock_identity(source) != (product, attributes):
                    continue
                order = source.order_id
                direct_moves = (order.picking_ids.move_ids | order.stock_reference_ids.move_ids).filtered(
                    lambda move: move.product_id == product
                    and move.never_product_template_attribute_value_ids == attributes
                    and move.location_dest_id.usage == "customer"
                    and move.state != "cancel"
                )
                if (not direct_moves and order.session_id.update_stock_at_closing
                        and order.session_id.state != "closed"
                        and not order.shipping_date and not order._force_create_picking_real_time()):
                    group["deferred"] |= source
        for group in groups.values():
            source_lines = group["lines"]
            product = source_lines.product_id
            moves = group["moves"]
            if moves.filtered(lambda move: move.company_id not in source_lines.company_id):
                raise UserError(self.env._("The stock source belongs to another company."))
            available = 0.0
            known_lots = set()
            for move in moves:
                if move.state == "done":
                    returned = move.returned_move_ids.filtered(lambda item: item.state == "done")
                    available += move.product_uom._compute_quantity(move.quantity, product.uom_id)
                    available -= sum(
                        item.product_uom._compute_quantity(item.quantity, product.uom_id)
                        for item in returned
                    )
                    known_lots.update(move.move_line_ids.lot_id.mapped("name"))
                elif any(line.order_id._get_correction_root().shipping_date for line in source_lines):
                    available += move.product_uom._compute_quantity(move.product_uom_qty, product.uom_id)
                    known_lots.update(source_lines.pack_lot_ids.mapped("lot_name"))
            for source in group["deferred"]:
                available += max(
                    source.correction_stock_qty if source.order_id.is_correction_order else source.qty,
                    0.0,
                )
                known_lots.update(source.pack_lot_ids.mapped("lot_name"))
            required = sum(source_lines.mapped("qty"))
            missing_quantity = required - available
            missing_lots = product.tracking != "none" and any(
                not line.pack_lot_ids
                or not set(line.pack_lot_ids.mapped("lot_name")).issubset(known_lots)
                for line in source_lines
            )
            if (missing_quantity > 0 and not product.uom_id.is_zero(missing_quantity)) or missing_lots:
                raise UserError(self.env._(
                    "The stock history for %(product)s does not identify the effective sold quantity.",
                    product=product.display_name,
                ))

    @api.model
    def _correction_physical_delta(self, line):
        quantity = line.correction_stock_qty
        names = line.pack_lot_ids.mapped("lot_name")
        source = line.correction_origin_line_id
        if not source or source.product_id != line.product_id:
            return quantity, names
        desired = line.order_id.correction_id.line_ids.filtered(
            lambda item: item.source_order_line_id == source
            and item.product_id == source.product_id
        )
        if line.qty > 0:
            previous_names = set(source.pack_lot_ids.mapped("lot_name"))
            current_names = set(names)
        else:
            previous_names = set(names)
            current_names = set(
                name.strip() for name in (desired.lot_names or "").splitlines()
                if name.strip()
            ) if desired else set()
        if line.product_id.tracking == "serial":
            changed = (current_names - previous_names) if line.qty > 0 else (
                previous_names - current_names
            )
            return len(changed) * (1 if line.qty > 0 else -1), sorted(changed)
        if line.product_id.tracking == "lot" and previous_names != current_names:
            return line.qty, names
        return quantity, names

    @api.model
    def _correction_create_completed_picking(
        self, location_dest_id, line, picking_type, partner, quantity, lot_names,
        source_move=None,
    ):
        if quantity < 0:
            operation_type = picking_type.return_picking_type_id or picking_type
            location_id = location_dest_id
            destination_id = (
                operation_type.default_location_dest_id.id
                if picking_type.return_picking_type_id
                else picking_type.default_location_src_id.id
            )
        else:
            operation_type = picking_type
            location_id = picking_type.default_location_src_id.id
            destination_id = location_dest_id
        picking = self.create(
            self._prepare_picking_vals(
                partner, operation_type, location_id, destination_id
            )
        )
        picking.with_context(**_stock_context(
            mode="move",
            source_move_id=source_move.id if source_move else False,
            quantities={line.id: quantity},
            lot_names={line.id: lot_names},
        ))._create_move_from_pos_order_lines(line)
        picking._action_done()
        if picking.state != "done":
            raise UserError(self.env._("The correction stock movement could not be completed."))
        return picking

    @api.model
    def _correction_reduce_pending(self, source, quantity, lot_names):
        moves = self._correction_matching_moves(source).filtered(
            lambda move: move.state not in ("done", "cancel")
        )
        remaining_names = set(lot_names)
        completed_names = set(self._correction_matching_moves(source).filtered(
            lambda move: move.state == "done"
        ).move_line_ids.lot_id.mapped("name"))
        for move in moves.sorted("id"):
            demand = move.product_uom._compute_quantity(
                move.product_uom_qty, source.product_uom_id
            )
            available = demand
            pending_names = remaining_names
            if source.product_id.tracking == "serial":
                pending_names = remaining_names - completed_names
                reserved_names = set(move.move_line_ids.lot_id.mapped("name"))
                if reserved_names:
                    pending_names &= reserved_names
                available = min(available, len(pending_names))
            reduce_quantity = min(quantity, available)
            if source.product_uom_id.is_zero(reduce_quantity):
                continue
            new_quantity = demand - reduce_quantity
            if source.product_uom_id.is_zero(new_quantity):
                move._action_cancel()
            else:
                move.product_uom_qty = source.product_uom_id._compute_quantity(
                    new_quantity, move.product_uom
                )
                if source.product_id.tracking != "none":
                    retained_names = set(source.pack_lot_ids.mapped("lot_name"))
                    if source.product_id.tracking == "serial":
                        retained_names -= set(lot_names) | completed_names
                    move._do_unreserve()
                    move.with_context(**_stock_context(
                        mode="move",
                        quantities={source.id: new_quantity},
                        lot_names={source.id: sorted(retained_names)},
                    ))._add_mls_related_to_order(source, are_qties_done=False)
                    move._recompute_state()
                else:
                    move._action_assign()
            if source.product_id.tracking == "serial":
                remaining_names -= set(sorted(pending_names)[:int(reduce_quantity)])
            quantity -= reduce_quantity
            if source.product_uom_id.is_zero(quantity):
                break
        return quantity, sorted(remaining_names)

    @api.model
    def _correction_return_completed(
        self, location_dest_id, line, source, quantity, lot_names, picking_type, partner
    ):
        moves = self._correction_matching_moves(source).filtered(
            lambda move: move.state == "done"
        )
        remaining_names = set(lot_names)
        pickings = self.env["stock.picking"]
        for move in moves.sorted(lambda item: (item.date, item.id), reverse=True):
            move_names = set(move.move_line_ids.lot_id.mapped("name"))
            names = sorted(remaining_names & move_names)
            if remaining_names and not names:
                continue
            returned = move.returned_move_ids.filtered(lambda item: item.state == "done")
            available = move.product_uom._compute_quantity(
                move.quantity, source.product_uom_id
            ) - sum(
                item.product_uom._compute_quantity(item.quantity, source.product_uom_id)
                for item in returned
            )
            if source.product_id.tracking == "serial":
                names = sorted(set(names) - set(returned.move_line_ids.lot_id.mapped("name")))
                available = min(available, len(names))
            elif remaining_names:
                available = min(available, sum(
                    item.product_uom_id._compute_quantity(
                        item.quantity, source.product_uom_id
                    )
                    for item in move.move_line_ids.filtered(
                        lambda item: item.lot_id.name in remaining_names
                    )
                ))
            return_quantity = min(quantity, max(available, 0.0))
            if source.product_uom_id.is_zero(return_quantity):
                continue
            if source.product_id.tracking == "serial":
                names = names[:int(return_quantity)]
            pickings |= self._correction_create_completed_picking(
                location_dest_id, line, picking_type, partner,
                -return_quantity, names, source_move=move,
            )
            remaining_names -= set(names)
            quantity -= return_quantity
            if source.product_uom_id.is_zero(quantity):
                break
        if not source.product_uom_id.is_zero(quantity):
            raise UserError(
                self.env._(
                    "The delivered stock source for %(product)s cannot be established.",
                    product=source.product_id.display_name,
                )
            )
        return pickings

    @api.model
    def _correction_create_pending(self, line, quantity, lot_names):
        order = line.order_id
        reference = order.stock_reference_ids
        if not reference:
            reference = self.env["stock.reference"].create(line._prepare_reference_vals())
            order.stock_reference_ids = [Command.link(reference.id)]
        values = line._prepare_procurement_values()
        root = order.correction_root_id
        source = root.lines.filtered(lambda item: item.product_id.type == "consu")[:1]
        if source and root.shipping_date:
            source_values = source._prepare_procurement_values()
            values.update({
                key: source_values[key] for key in ("date_planned", "date_deadline")
            })
        procurement = self.env["stock.rule"].Procurement(
            line.product_id, quantity, line.product_uom_id,
            order.partner_id.property_stock_customer,
            line.name, order.name, order.company_id, values,
        )
        old_moves = reference.move_ids
        self.env["stock.rule"].run([procurement])
        moves = reference.move_ids - old_moves
        moves.picking_id.action_confirm()
        if line.product_id.tracking != "none":
            tracked_moves = moves.filtered(
                lambda move: move.product_id == line.product_id
                and move.location_dest_id.usage == "customer"
            )
            tracked_moves.move_line_ids.unlink()
            tracked_moves.with_context(**_stock_context(
                mode="move",
                quantities={line.id: quantity},
                lot_names={line.id: lot_names},
            ))._add_mls_related_to_order(line, are_qties_done=False)
            tracked_moves._recompute_state()
        return moves.picking_id

    @api.model
    def _create_picking_from_pos_order_lines(
        self, location_dest_id, lines, picking_type, partner=False
    ):
        stock_context = _stock_context_values(self.env)
        if stock_context.get("mode") == "session_closing":
            return self._create_correction_aware_closing_picking(
                location_dest_id, lines, picking_type, partner
            )
        correction_lines = lines.filtered(lambda line: line.order_id.is_correction_order)
        corrected_returns = (lines - correction_lines).filtered(
            lambda line: line.refunded_orderline_id
            and (
                line.refunded_orderline_id.order_id.correction_root_id
                or line.refunded_orderline_id.order_id.correction_ids.filtered(
                    lambda correction: correction.state == "applied"
                )
            )
        )
        corrected_returns._check_correction_refund_quantities()
        ordinary_lines = lines - correction_lines - corrected_returns
        pickings = super()._create_picking_from_pos_order_lines(
            location_dest_id, ordinary_lines, picking_type, partner
        )
        if stock_context.get("mode") == "closing_lines":
            self._link_closing_moves_to_orders(ordinary_lines, pickings.move_ids)
            quantities = stock_context["quantities"]
            names_by_line = stock_context["lot_names"]
        else:
            quantities = {}
            names_by_line = {}
        for line in correction_lines | corrected_returns:
            if line.product_id.type != "consu":
                continue
            if line in correction_lines:
                quantity, lot_names = self._correction_physical_delta(line)
                quantity = quantities.get(line.id, quantity)
                lot_names = names_by_line.get(line.id, lot_names)
            else:
                quantity, lot_names = line.qty, line.pack_lot_ids.mapped("lot_name")
            if line.product_uom_id.is_zero(quantity):
                continue
            if quantity > 0:
                if line.order_id.correction_root_id.shipping_date:
                    pickings |= self._correction_create_pending(line, quantity, lot_names)
                else:
                    delivered = self._correction_create_completed_picking(
                        location_dest_id, line, picking_type, partner, quantity, lot_names
                    )
                    self._link_closing_moves_to_orders(line, delivered.move_ids)
                    pickings |= delivered
            else:
                service = self.with_context(
                    pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN
                ) if line in corrected_returns else self
                source = line.correction_origin_line_id or line.refunded_orderline_id
                remaining, remaining_lots = service._correction_reduce_pending(
                    source, -quantity, lot_names
                )
                if not line.product_uom_id.is_zero(remaining):
                    returned = service._correction_return_completed(
                        location_dest_id, line, source, remaining,
                        remaining_lots, picking_type, partner,
                    )
                    self._link_closing_moves_to_orders(line, returned.move_ids)
                    pickings |= returned
        return pickings

    @api.model
    def _create_correction_aware_closing_picking(
        self, location_dest_id, lines, picking_type, partner=False
    ):
        roots = lines.order_id.filtered("is_correction_order").correction_root_id
        deferred_roots = roots.filtered(lambda root: root in lines.order_id)
        effective_lines = self.env["pos.order.line"]
        for root in deferred_roots:
            chain = root._get_correction_chain()
            lines -= chain.lines
            for line in root._get_effective_correction_lines():
                effective_lines |= line
        # Effective deferred demands are ordinary physical lines. Other sales and
        # customer returns retain the standard stock path without being discarded.
        quantities = {}
        names_by_line = {}
        correction_lines = lines.filtered(lambda line: line.order_id.is_correction_order)
        for line in correction_lines:
            quantities[line.id], names_by_line[line.id] = self._correction_physical_delta(line)
        for line in correction_lines.filtered(lambda item: quantities[item.id] < 0):
            remaining = -quantities[line.id]
            sources = self._correction_stock_ancestors(line.correction_origin_line_id)
            for source in sources:
                available = quantities.get(source.id, 0.0)
                if available <= 0 or source.product_id != line.product_id:
                    continue
                consumed = min(remaining, available)
                if line.product_id.tracking == "serial":
                    names = set(names_by_line[line.id]) & set(names_by_line[source.id])
                    consumed = min(consumed, len(names))
                    consumed_names = set(sorted(names)[:int(consumed)])
                    names_by_line[line.id] = sorted(set(names_by_line[line.id]) - consumed_names)
                    names_by_line[source.id] = sorted(set(names_by_line[source.id]) - consumed_names)
                quantities[source.id] -= consumed
                remaining -= consumed
                if line.product_uom_id.is_zero(remaining):
                    break
            quantities[line.id] = -remaining
        context = _stock_context(
            mode="closing_lines", quantities=quantities, lot_names=names_by_line
        )
        pickings = self.with_context(**context)._create_picking_from_pos_order_lines(
            location_dest_id, lines, picking_type, partner
        )
        if effective_lines:
            effective_context = _stock_context(
                mode="move",
                quantities={line.id: line.qty for line in effective_lines},
                lot_names={
                    line.id: line.pack_lot_ids.mapped("lot_name") for line in effective_lines
                },
            )
            effective_pickings = super(StockPicking, self.with_context(**effective_context))._create_picking_from_pos_order_lines(
                location_dest_id, effective_lines, picking_type, partner
            )
            if any(picking.state != "done" for picking in effective_pickings):
                raise UserError(self.env._("The session delivery could not be completed."))
            self._link_closing_moves_to_orders(effective_lines, effective_pickings.move_ids)
            pickings |= effective_pickings
        return pickings

    @api.model
    def _link_closing_moves_to_orders(self, lines, moves):
        for order in lines.order_id:
            order_lines = lines.filtered(lambda line: line.order_id == order)
            reference = order.stock_reference_ids[:1]
            if not reference:
                reference = self.env["stock.reference"].create(order_lines[0]._prepare_reference_vals())
                order.stock_reference_ids = [Command.link(reference.id)]
            for line in order_lines:
                product, attributes = self._correction_stock_identity(line)
                matching = moves.filtered(
                    lambda move: move.product_id == product
                    and move.never_product_template_attribute_value_ids == attributes
                    and (move.location_dest_id.usage == "customer") == (line.qty > 0)
                )
                matching.reference_ids = [Command.link(reference.id)]

    def _prepare_stock_move_vals(self, first_line, order_lines):
        values = super()._prepare_stock_move_vals(first_line, order_lines)
        stock_context = _stock_context_values(self.env)
        if stock_context.get("mode") == "move":
            quantities = stock_context["quantities"]
            values["product_uom_qty"] = abs(sum(
                quantities.get(line.id, line.qty) for line in order_lines
            ))
            values["origin_returned_move_id"] = stock_context.get("source_move_id", False)
        return values


class StockMoveCorrection(models.Model):
    _inherit = "stock.move"

    def _add_mls_related_to_order(self, related_order_lines, are_qties_done=True):
        stock_context = _stock_context_values(self.env)
        if stock_context.get("mode") != "move":
            return super()._add_mls_related_to_order(related_order_lines, are_qties_done)
        tracked_moves = self.filtered(
            lambda move: move.product_id.tracking != "none"
            and (move.picking_type_id.use_existing_lots or move.picking_type_id.use_create_lots)
        )
        super(StockMoveCorrection, self - tracked_moves)._add_mls_related_to_order(
            related_order_lines, are_qties_done
        )
        if not tracked_moves:
            return
        quantities = stock_context["quantities"]
        names_by_line = stock_context["lot_names"]
        lots = tracked_moves._create_production_lots_for_pos_order(related_order_lines)
        values_list = []
        for move in tracked_moves:
            if are_qties_done:
                move.move_line_ids.unlink()
            lines = related_order_lines.filtered(
                lambda line: line.product_id == move.product_id
                and line.attribute_value_ids.filtered(
                    lambda value: value.attribute_id.create_variant == "no_variant"
                ) == move.never_product_template_attribute_value_ids
            )
            for line in lines:
                names = names_by_line.get(line.id, line.pack_lot_ids.mapped("lot_name"))
                for name in names:
                    quantity = 1 if line.product_id.tracking == "serial" else abs(
                        quantities.get(line.id, line.qty)
                    )
                    lot = lots.filtered(
                        lambda item: item.product_id == line.product_id and item.name == name
                    )
                    if not lot:
                        raise UserError(self.env._("The stock lot %(lot)s could not be identified.", lot=name))
                    if not are_qties_done:
                        move._update_reserved_quantity(quantity, move.location_id, lot_id=lot)
                        continue
                    quants = self.env["stock.quant"].search([
                        ("lot_id", "=", lot.id),
                        ("quantity", ">", 0),
                        ("location_id", "child_of", move.location_id.id),
                    ], order="id desc")
                    for quant in quants:
                        assigned = min(quantity, quant.quantity)
                        if assigned <= 0:
                            break
                        values = move._prepare_move_line_vals(assigned)
                        values["quant_id"] = quant.id
                        values_list.append(values)
                        quantity -= assigned
                    if quantity > 0:
                        values = move._prepare_move_line_vals(quantity)
                        values.update({"lot_id": lot.id, "lot_name": lot.name})
                        values_list.append(values)
        if values_list:
            self.env["stock.move.line"].create(values_list)


class PosSessionStock(models.Model):
    _inherit = "pos.session"

    def _create_picking_at_end_of_session(self):
        return super(PosSessionStock, self.with_context(**_stock_context(
            mode="session_closing"
        )))._create_picking_at_end_of_session()


class PosOrderStock(models.Model):
    _inherit = "pos.order"

    def _check_correction_eligibility(self):
        result = super()._check_correction_eligibility()
        for order in self:
            self.env["stock.picking"]._check_correction_stock_sources(
                order._get_effective_correction_lines()
            )
        return result

    def _force_create_picking_real_time(self):
        return super()._force_create_picking_real_time() or bool(
            self.is_correction_order and self.correction_root_id.shipping_date
        )

    def _create_order_picking(self):
        self.ensure_one()
        if not (self.is_correction_order and self.correction_root_id.shipping_date):
            return super()._create_order_picking()
        if self.picking_ids:
            return
        picking_type = self.config_id.picking_type_id
        destination = self.partner_id.property_stock_customer or picking_type.default_location_dest_id
        pickings = self.env["stock.picking"]._create_picking_from_pos_order_lines(
            destination.id, self.lines, picking_type, self.partner_id
        )
        pickings.write({
            "pos_session_id": self.session_id.id,
            "pos_order_id": self.id,
            "origin": self.name,
        })
