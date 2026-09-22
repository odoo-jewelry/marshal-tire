from odoo import models, fields, api


class HrPersonalFile(models.Model):
    _name = 'hr.personal.file'
    _description = 'Personal File'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'employee_id'

    name = fields.Char(
        string='File Number',
        required=True,
        default='New',
        tracking=True
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        tracking=True
    )

    # === Related fields from hr.employee (Odoo core) ===
    birth_place = fields.Char(
        string='Birth Place',
        related='employee_id.place_of_birth',
        readonly=False,
        store=False
    )
    country_of_birth = fields.Many2one(
        'res.country',
        string='Country of Birth',
        related='employee_id.country_of_birth',
        readonly=False,
        store=False
    )

    # === Related fields from hr.employee (l10n_ua_hr_base) ===
    education_level_id = fields.Many2one(
        'hr.education.level',
        string='Education Level',
        related='employee_id.education_level_id',
        readonly=False,
        store=False
    )
    # Use Odoo core fields for education
    education_institution = fields.Char(
        string='Educational Institution',
        related='employee_id.study_school',
        readonly=False,
        store=False
    )
    education_specialty = fields.Char(
        string='Specialty',
        related='employee_id.study_field',
        readonly=False,
        store=False
    )

    # Additional education fields (stored on personal file)
    graduation_year = fields.Integer(string='Graduation Year')
    qualification = fields.Char(string='Qualification')

    # === Military fields - related from hr.employee (l10n_ua_hr_base) ===
    military_status = fields.Selection(
        related='employee_id.military_status',
        readonly=False,
        store=False
    )
    military_rank_id = fields.Many2one(
        'hr.military.rank',
        string='Military Rank',
        related='employee_id.military_rank_id',
        readonly=False,
        store=False
    )
    military_specialty = fields.Char(
        string='Military Specialty',
        related='employee_id.military_specialty',
        readonly=False,
        store=False
    )

    # === Marital status - related from hr.employee (Odoo core) ===
    marital_status = fields.Selection(
        related='employee_id.marital',
        readonly=False,
        store=False
    )
    
    family_member_ids = fields.One2many(
        'hr.personal.file.family',
        'personal_file_id',
        string='Family Members'
    )
    
    document_ids = fields.One2many(
        'hr.personal.file.document',
        'personal_file_id',
        string='Documents'
    )
    
    work_history_ids = fields.One2many(
        'hr.personal.file.work.history',
        'personal_file_id',
        string='Work History'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.personal.file') or 'New'
        return super().create(vals_list)

    _unique_employee_id = models.Constraint(
        'unique(employee_id)',
        'Personal file for this employee already exists!',
    )


class HrPersonalFileFamily(models.Model):
    _name = 'hr.personal.file.family'
    _description = 'Family Member'
    _order = 'relation'

    personal_file_id = fields.Many2one(
        'hr.personal.file',
        string='Personal File',
        required=True,
        ondelete='cascade'
    )
    
    name = fields.Char(string='Full Name', required=True)
    relation = fields.Selection([
        ('spouse', 'Spouse'),
        ('child', 'Child'),
        ('parent', 'Parent'),
        ('other', 'Other'),
    ], string='Relation', required=True)
    birth_date = fields.Date(string='Birth Date')
    birth_place = fields.Char(string='Birth Place')


class HrPersonalFileDocument(models.Model):
    _name = 'hr.personal.file.document'
    _description = 'Personal File Document'
    _order = 'date desc'

    personal_file_id = fields.Many2one(
        'hr.personal.file',
        string='Personal File',
        required=True,
        ondelete='cascade'
    )
    
    document_type = fields.Selection([
        ('passport', 'Passport'),
        ('id_card', 'ID Card'),
        ('rnokpp', 'RNOKPP Certificate'),
        ('diploma', 'Diploma'),
        ('certificate', 'Certificate'),
        ('military', 'Military Document'),
        ('medical', 'Medical Certificate'),
        ('photo', 'Photo'),
        ('other', 'Other'),
    ], string='Document Type', required=True)
    
    name = fields.Char(string='Document Name')
    number = fields.Char(string='Document Number')
    date = fields.Date(string='Issue Date')
    issued_by = fields.Char(string='Issued By')
    valid_until = fields.Date(string='Valid Until')
    
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Attachment'
    )
    notes = fields.Char(string='Notes')


class HrPersonalFileWorkHistory(models.Model):
    _name = 'hr.personal.file.work.history'
    _description = 'Work History Entry'
    _order = 'date_from desc'

    personal_file_id = fields.Many2one(
        'hr.personal.file',
        string='Personal File',
        required=True,
        ondelete='cascade'
    )
    
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To')
    
    organization = fields.Char(string='Organization', required=True)
    position = fields.Char(string='Position')
    
    order_number = fields.Char(string='Order Number')
    order_date = fields.Date(string='Order Date')
    
    entry_type = fields.Selection([
        ('hire', 'Hiring'),
        ('transfer', 'Transfer'),
        ('termination', 'Termination'),
    ], string='Entry Type', required=True)
    
    notes = fields.Char(string='Notes')
