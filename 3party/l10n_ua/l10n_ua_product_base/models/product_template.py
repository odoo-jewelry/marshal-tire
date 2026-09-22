import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# УКТ ЗЕД is a ten-digit nomenclature read in pairs: group, heading,
# subheading, category, subcategory. A tax invoice may state it truncated to
# one of those levels — Порядок 1307 п. 16 requires "не менше ніж чотири перших
# цифри", and ten digits for excisable and imported goods. Anything else (five
# digits, a typo'd nine) is not a level of the classifier and ЄРПН rejects it.
UKTZED_LEVELS = (4, 6, 8, 10)

# Everything that is written between the digits when a code is copied from a
# customs document or a supplier's price list: "8471.30.00.00", "8471 30 00 00".
UKTZED_SEPARATORS = re.compile(r'[\s.\-_]+')

# ДКПП (ДК 016:2010) is read as dotted two-digit pairs — section, division,
# group, class, category — and the dash tail (subcategory, type) only appears
# once all three dotted pairs are there: 62.01.11-00.00. A code is quoted at
# whatever depth the document needs, so the tail is optional, but "62-01" is
# not a shorter form of anything — it is a typo.
# This checks the shape only: whether the code exists in the classifier is not
# something we can tell without the classifier itself, which this module does
# not carry.
DKPP_PATTERN = re.compile(
    r'^\d{2}(\.\d{2}){0,2}$'
    r'|^\d{2}\.\d{2}\.\d{2}-\d{2}(\.\d{2})?$'
)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    uktzed_code = fields.Char(
        string='UKTZED Code',
        help='Goods code under the Ukrainian Classification of Goods for '
             'Foreign Economic Activity. Box 3.1 of a tax invoice, mandatory '
             'for goods. Stated at 4, 6, 8 or 10 digits; imported and '
             'excisable goods need all ten.',
    )
    dkpp_code = fields.Char(
        string='DKPP Code',
        help='Service code under the Classifier of Products and Services '
             '(DK 016:2010), e.g. 62.01.11-00.00. Box 3.3 of a tax invoice, '
             'mandatory for services.',
    )

    @api.model
    def _l10n_ua_normalize_uktzed(self, code):
        """Strip the separators a code picks up in transit, keep the digits.

        The stored value is what goes into the ЄРПН XML and the PRRO receipt,
        and both want bare digits. Normalising on write rather than on render
        means the constraint below judges the same string the documents use.
        """
        if not code:
            return code
        return UKTZED_SEPARATORS.sub('', code.strip())

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'uktzed_code' in vals:
                vals['uktzed_code'] = self._l10n_ua_normalize_uktzed(vals['uktzed_code'])
            if 'dkpp_code' in vals and vals['dkpp_code']:
                vals['dkpp_code'] = vals['dkpp_code'].strip()
        return super().create(vals_list)

    def write(self, vals):
        if 'uktzed_code' in vals:
            vals['uktzed_code'] = self._l10n_ua_normalize_uktzed(vals['uktzed_code'])
        if 'dkpp_code' in vals and vals['dkpp_code']:
            vals['dkpp_code'] = vals['dkpp_code'].strip()
        return super().write(vals)

    @api.constrains('uktzed_code')
    def _check_uktzed_code(self):
        for product in self:
            code = product.uktzed_code
            if not code:
                continue
            if not code.isdigit():
                raise ValidationError(_(
                    'UKTZED code of "%(product)s" must contain digits only, '
                    'got "%(code)s".',
                    product=product.display_name, code=code,
                ))
            if len(code) not in UKTZED_LEVELS:
                raise ValidationError(_(
                    'UKTZED code of "%(product)s" is %(length)s digits long. '
                    'The classifier has levels of 4, 6, 8 and 10 digits; a '
                    'code of any other length is not a level of it and will '
                    'be rejected on registration.',
                    product=product.display_name, length=len(code),
                ))

    @api.constrains('dkpp_code')
    def _check_dkpp_code(self):
        for product in self:
            code = product.dkpp_code
            if code and not DKPP_PATTERN.match(code):
                raise ValidationError(_(
                    'DKPP code of "%(product)s" must look like 62.01.11-00.00 '
                    '(two-digit groups, dot-separated, an optional dash before '
                    'the last two), got "%(code)s".',
                    product=product.display_name, code=code,
                ))

    def _l10n_ua_product_codes(self):
        """The statutory code pair for one document line, as field values.

        УКТ ЗЕД classifies goods and ДКПП classifies services, and a tax
        invoice line carries exactly one of them — box 3.1 or box 3.3, per
        Порядок 1307 п. 16. So the product type decides which, and the other
        key comes back empty rather than absent: a document line rebuilt from
        a product must overwrite a stale code, not leave it standing.

        Returns the keys unset for an empty recordset, which is what a line
        without a product gets.
        """
        if not self:
            return {'uktzed_code': False, 'dkpp_code': False}
        self.ensure_one()
        if self.type == 'service':
            return {'uktzed_code': False, 'dkpp_code': self.dkpp_code or False}
        return {'uktzed_code': self.uktzed_code or False, 'dkpp_code': False}


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _l10n_ua_product_codes(self):
        """Same as on the template — `_inherits` delegates fields, not methods,
        and every document line holds a variant, not a template."""
        return self.product_tmpl_id._l10n_ua_product_codes()
