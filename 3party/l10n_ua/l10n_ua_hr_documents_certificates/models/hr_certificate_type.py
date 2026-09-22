from odoo import models, fields, api


class HrCertificateType(models.Model):
    _name = 'hr.certificate.type'
    _description = 'HR Certificate Type'
    _order = 'sequence, name'

    name = fields.Char(
        string='Name',
        required=True,
        translate=True
    )
    code = fields.Char(
        string='Code',
        required=True
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    description = fields.Text(
        string='Description',
        translate=True
    )

    # Sequence for numbering
    sequence_id = fields.Many2one(
        'ir.sequence',
        string='Document Sequence',
        help='Sequence used for numbering certificates of this type'
    )

    # Template settings
    template_body = fields.Html(
        string='Template Body',
        translate=True,
        sanitize=False,
        help="""Available placeholders:
        {company_name} - Company name
        {company_director} - Company director name
        {company_director_position} - Director position
        {company_address} - Company address
        {company_edrpou} - Company EDRPOU code
        {company_phone} - Company phone
        {employee_name} - Employee full name
        {employee_name_genitive} - Employee name in genitive case
        {employee_position} - Employee job position
        {employee_department} - Employee department
        {employee_hire_date} - Hire date
        {employee_rnokpp} - Employee RNOKPP (Tax ID)
        {employee_passport} - Employee passport
        {salary_amount} - Current salary
        {salary_words} - Salary in words
        {work_experience} - Work experience at company
        {certificate_number} - Certificate number
        {certificate_date} - Certificate issue date
        {certificate_date_words} - Issue date in words
        {destination} - Certificate destination (за місцем вимоги)
        {period_from} - Period start (for salary certificates)
        {period_to} - Period end (for salary certificates)
        {total_income} - Total income for period
        {total_income_words} - Total income in words
        {current_date} - Current date
        """
    )

    # Certificate settings
    requires_salary_info = fields.Boolean(
        string='Requires Salary Information',
        help='If checked, salary data will be included'
    )
    requires_period = fields.Boolean(
        string='Requires Period',
        help='If checked, period dates are required'
    )
    requires_destination = fields.Boolean(
        string='Requires Destination',
        default=True,
        help='If checked, destination field is required'
    )
    validity_days = fields.Integer(
        string='Validity (days)',
        default=30,
        help='Number of days the certificate is valid'
    )

    # Report template
    report_id = fields.Many2one(
        'ir.actions.report',
        string='Report Template',
        domain="[('model', '=', 'hr.certificate')]",
        help='Custom report template for this certificate type'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    # Statistics
    certificates_count = fields.Integer(
        string='Certificates Count',
        compute='_compute_certificates_count'
    )

    _unique_code_company = models.Constraint(
        'UNIQUE(code, company_id)',
        'Certificate type code must be unique per company!',
    )

    def _compute_certificates_count(self):
        for record in self:
            record.certificates_count = self.env['hr.certificate'].search_count([
                ('certificate_type_id', '=', record.id)
            ])

    @api.model
    def create(self, vals):
        """Create sequence for new certificate type if not provided"""
        record = super().create(vals)
        if not record.sequence_id:
            record._create_sequence()
        return record

    def _create_sequence(self):
        """Create a sequence for this certificate type"""
        self.ensure_one()
        sequence_vals = {
            'name': f'HR Certificate: {self.name}',
            'code': f'hr.certificate.{self.code}',
            'prefix': f'Д-{self.code.upper()}-%(year)s/',
            'padding': 4,
            'company_id': self.company_id.id if self.company_id else False,
        }
        sequence = self.env['ir.sequence'].create(sequence_vals)
        self.sequence_id = sequence.id

    def action_view_certificates(self):
        """View certificates of this type"""
        self.ensure_one()
        return {
            'name': self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'hr.certificate',
            'view_mode': 'list,form',
            'domain': [('certificate_type_id', '=', self.id)],
            'context': {'default_certificate_type_id': self.id},
        }
