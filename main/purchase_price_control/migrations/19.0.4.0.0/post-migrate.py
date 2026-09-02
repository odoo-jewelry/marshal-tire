def migrate(cr, _version):
    # ORM cannot address the legacy snapshot semantics before this upgrade.
    cr.execute(
        """
        UPDATE purchase_order_line AS line
           SET current_markup = CASE
                   WHEN line.current_standard_price > 0
                   THEN (line.current_sale_price / line.current_standard_price - 1.0) * 100.0
                   ELSE company.purchase_default_markup
               END
          FROM purchase_order AS purchase,
               res_company AS company
         WHERE purchase.id = line.order_id
           AND company.id = purchase.company_id
           AND line.price_snapshot_initialized
           AND line.product_id IS NOT NULL
           AND line.display_type IS NULL
           AND NOT COALESCE(line.is_downpayment, FALSE)
        """
    )
