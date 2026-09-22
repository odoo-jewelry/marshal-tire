import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .checkbox_api import CheckboxAPI, parse_checkbox_datetime

_logger = logging.getLogger(__name__)


class L10nUaPrroCheckboxConfig(models.Model):
    _name = 'l10n_ua.prro.checkbox.config'
    _description = 'Checkbox PRRO Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    prro_config_id = fields.Many2one(
        'l10n_ua.prro.config',
        string='PRRO Configuration',
    )
    
    # Checkbox API credentials
    auth_type = fields.Selection(
        selection=[
            ('login', 'Login and Password'),
            ('pin', 'PIN Code'),
        ],
        string='Authentication Type',
        default='login',
        required=True,
    )
    license_key = fields.Char(
        string='License Key',
        help='Cash register license key from Checkbox',
    )
    cashier_login = fields.Char(
        string='Cashier Login',
    )
    cashier_password = fields.Char(
        string='Cashier Password',
    )
    cashier_pin = fields.Char(
        string='Cashier PIN',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._clean_auth_fields(vals)
        return super().create(vals_list)

    def write(self, vals):
        if 'auth_type' in vals:
            self._clean_auth_fields(vals)
        return super().write(vals)

    def _clean_auth_fields(self, vals):
        auth_type = vals.get('auth_type')
        if auth_type == 'pin':
            vals['cashier_login'] = False
            vals['cashier_password'] = False
        elif auth_type == 'login':
            vals['cashier_pin'] = False
    
    # Cash register info (from API)
    cash_register_id = fields.Char(
        string='Cash Register ID',
        readonly=True,
    )
    cash_register_fiscal_number = fields.Char(
        string='Fiscal Number',
        readonly=True,
    )
    cash_register_name = fields.Char(
        string='Cash Register Name',
        readonly=True,
    )
    
    # Cashier info (from API)
    cashier_id = fields.Char(
        string='Cashier ID',
        readonly=True,
    )
    cashier_name = fields.Char(
        string='Cashier Name',
        readonly=True,
    )
    
    # State
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('configured', 'Configured'),
            ('authenticated', 'Authenticated'),
            ('error', 'Error'),
        ],
        string='State',
        default='draft',
        tracking=True,
    )
    access_token = fields.Char(
        string='Access Token',
    )
    token_expiry = fields.Datetime(
        string='Token Expiry',
    )
    error_message = fields.Text(
        string='Error Message',
        readonly=True,
    )
    
    # Current shift
    current_shift_id = fields.Many2one(
        'l10n_ua.prro.shift',
        string='Current Shift',
        compute='_compute_current_shift',
    )
    is_shift_open = fields.Boolean(
        string='Shift Open',
        compute='_compute_current_shift',
    )

    def _compute_current_shift(self):
        for config in self:
            shift = self.env['l10n_ua.prro.shift'].search([
                ('config_id.prro_config_id', '=', config.prro_config_id.id),
                ('state', '=', 'open'),
            ], limit=1)
            config.current_shift_id = shift
            config.is_shift_open = bool(shift)

    def _get_api(self):
        """Get configured Checkbox API client."""
        self.ensure_one()
        return CheckboxAPI(
            license_key=self.license_key,
            access_token=self.access_token,
        )

    def _clear_error(self):
        self.write({'error_message': False})

    def _set_error(self, message):
        self.write({
            'state': 'error',
            'error_message': message,
        })

    def action_authenticate(self):
        """Authenticate cashier with Checkbox API."""
        self.ensure_one()
        self._clear_error()

        try:
            api = CheckboxAPI(
                license_key=self.license_key,
            )
            if self.auth_type == 'pin':
                if not self.cashier_pin:
                    raise UserError(_('Please provide cashier PIN code.'))
                response = api.cashier_signin_pincode(self.cashier_pin)
            else:
                if not self.cashier_login or not self.cashier_password:
                    raise UserError(_('Please provide cashier login and password.'))
                response = api.cashier_signin_login_password(self.cashier_login, self.cashier_password)

            self.write({
                'access_token': response.get('access_token'),
                'token_expiry': fields.Datetime.now() + timedelta(weeks=1),
                'state': 'authenticated',
            })

            # Get cashier info
            cashier_info = api.cashier_me()
            self.write({
                'cashier_id': cashier_info.get('id'),
                'cashier_name': cashier_info.get('full_name'),
            })

            # Get cash register info
            if self.license_key:
                register_info = api.get_cash_register_info()
                self.write({
                    'cash_register_id': register_info.get('id'),
                    'cash_register_fiscal_number': register_info.get('fiscal_number'),
                    'cash_register_name': register_info.get('title'),
                })

            self.message_post(body=_('Successfully authenticated with Checkbox API.'))

        except Exception as e:
            self._set_error(str(e))
            raise

    def action_signout(self):
        """Sign out from Checkbox API."""
        self.ensure_one()
        if self.access_token:
            try:
                api = self._get_api()
                api.cashier_signout()
            except Exception:
                pass
        self.write({
            'access_token': False,
            'token_expiry': False,
            'state': 'configured' if self.license_key else 'draft',
        })
        self.message_post(body=_('Signed out from Checkbox API.'))

    def action_open_shift(self):
        """Open fiscal shift."""
        self.ensure_one()
        self._clear_error()

        if not self.access_token:
            raise UserError(_('Please authenticate first.'))

        try:
            api = self._get_api()
            
            # Check if shift already open
            current_shift = api.get_shift()
            if current_shift:
                raise UserError(_('Shift is already open. Close it first.'))

            response = api.open_shift()
            
            # Create shift record
            shift_vals = {
                'config_id': self.prro_config_id.id,
                'shift_number': response.get('serial'),
                'open_date': parse_checkbox_datetime(response.get('opened_at')),
                'state': 'open',
            }
            shift = self.env['l10n_ua.prro.shift'].create(shift_vals)
            
            self.message_post(body=_('Shift #%s opened.', response.get('serial')))
            return shift

        except Exception as e:
            self._set_error(str(e))
            raise

    def action_close_shift(self):
        """Close fiscal shift (Z-report)."""
        self.ensure_one()
        self._clear_error()

        if not self.access_token:
            raise UserError(_('Please authenticate first.'))

        try:
            api = self._get_api()
            response = api.close_shift()
            
            z_report = response.get('z_report', {})
            
            # Update shift record
            if self.current_shift_id:
                self.current_shift_id.write({
                    'state': 'closed',
                    'close_date': fields.Datetime.now(),
                    'z_report_number': z_report.get('serial'),
                })

            self.message_post(body=_('Shift closed. Z-Report #%s', z_report.get('serial')))
            return response

        except Exception as e:
            self._set_error(str(e))
            raise

    def action_x_report(self):
        """Generate X-report."""
        self.ensure_one()
        self._clear_error()

        if not self.access_token:
            raise UserError(_('Please authenticate first.'))

        try:
            api = self._get_api()
            response = api.create_x_report()
            
            self.message_post(body=_('X-Report generated.'))
            return response

        except Exception as e:
            self._set_error(str(e))
            raise

    def action_register_receipt(self, receipt_data):
        """Register fiscal receipt."""
        self.ensure_one()
        self._clear_error()

        if not self.access_token:
            raise UserError(_('Please authenticate first.'))

        try:
            api = self._get_api()
            response = api.create_receipt(receipt_data)

            # Create receipt record. `total_amount` is a stored computed field
            # (cash + card), so the payment split must be populated — otherwise
            # the total stays 0 and the API `total_sum` is lost. Prefer the sent
            # tender (`receipt_data`), fall back to the fiscalised response.
            Receipt = self.env['l10n_ua.prro.receipt']
            receipt_vals = {
                'shift_id': self.current_shift_id.id,
                'fiscal_number': response.get('fiscal_code'),
                'local_number': response.get('serial'),
                'receipt_type': 'sale',
                'state': 'registered',
            }
            payments = receipt_data.get('payments') or response.get('payments')
            receipt_vals.update(Receipt._prepare_payment_vals(payments))
            receipt = Receipt.create(receipt_vals)

            return receipt

        except Exception as e:
            self._set_error(str(e))
            raise

    def action_service_input(self, amount):
        """Service cash input."""
        self.ensure_one()
        self._clear_error()

        if not self.access_token:
            raise UserError(_('Please authenticate first.'))

        try:
            api = self._get_api()
            receipt_data = {
                'payment': {
                    'type': 'CASH',
                    'value': int(amount * 100),
                }
            }
            response = api.create_service_receipt(receipt_data)
            
            self.message_post(body=_('Service input: %.2f UAH', amount))
            return response

        except Exception as e:
            self._set_error(str(e))
            raise

    def action_service_output(self, amount):
        """Service cash output."""
        self.ensure_one()
        self._clear_error()

        if not self.access_token:
            raise UserError(_('Please authenticate first.'))

        try:
            api = self._get_api()
            receipt_data = {
                'payment': {
                    'type': 'CASH',
                    'value': -int(amount * 100),
                }
            }
            response = api.create_service_receipt(receipt_data)
            
            self.message_post(body=_('Service output: %.2f UAH', amount))
            return response

        except Exception as e:
            self._set_error(str(e))
            raise

    def action_test_connection(self):
        """Test API connection."""
        self.ensure_one()
        self._clear_error()

        try:
            api = self._get_api()
            api.ping_tax_service()
            
            self.message_post(body=_('Connection test successful.'))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Connection to Checkbox API is working.'),
                    'type': 'success',
                }
            }

        except Exception as e:
            self._set_error(str(e))
            raise

    def action_sync_taxes(self):
        """Sync tax rates from Checkbox."""
        self.ensure_one()
        self._clear_error()

        if not self.access_token:
            raise UserError(_('Please authenticate first.'))

        try:
            api = self._get_api()
            taxes = api.get_taxes()
            
            self.message_post(body=_('Synced %d tax rates from Checkbox.', len(taxes)))
            return taxes

        except Exception as e:
            self._set_error(str(e))
            raise
