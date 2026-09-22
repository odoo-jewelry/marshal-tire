from odoo import api, fields, models


class L10nUaMealMenu(models.Model):
    """Меню (один день)."""
    _name = 'l10n_ua.meal.menu'
    _description = 'Меню на день'
    _order = 'menu_date desc, age_group'

    name = fields.Char(string='Назва', compute='_compute_name', store=True)
    menu_date = fields.Date(string='Дата', required=True, default=fields.Date.context_today)
    age_group = fields.Selection([
        ('zdo_1_3', 'ЗДО 1-3 роки'),
        ('zdo_3_6', 'ЗДО 3-6 років'),
        ('school_1_4', 'Школа 1-4 класи'),
        ('school_5_11', 'Школа 5-11 класи'),
    ], string='Вікова група', required=True)
    company_id = fields.Many2one('res.company', required=True,
                                   default=lambda self: self.env.company)
    line_ids = fields.One2many('l10n_ua.meal.menu.line', 'menu_id', string='Страви',
                                 copy=True)
    total_calories = fields.Float(string='Усього ккал',
                                    compute='_compute_totals', store=True)
    total_protein = fields.Float(string='Усього білки, г',
                                   compute='_compute_totals', store=True)
    total_fat = fields.Float(string='Усього жири, г',
                               compute='_compute_totals', store=True)
    total_carbohydrate = fields.Float(string='Усього вуглеводи, г',
                                        compute='_compute_totals', store=True)
    state = fields.Selection([
        ('draft', 'Чернетка'),
        ('approved', 'Затверджено'),
    ], default='draft', required=True)
    note = fields.Text(string='Примітки')

    @api.depends('menu_date', 'age_group')
    def _compute_name(self):
        for rec in self:
            label = dict(self._fields['age_group'].selection).get(rec.age_group) or ''
            rec.name = f'{rec.menu_date} — {label}' if rec.menu_date else label

    @api.depends('line_ids.calories', 'line_ids.protein', 'line_ids.fat',
                  'line_ids.carbohydrate')
    def _compute_totals(self):
        for rec in self:
            rec.total_calories = sum(rec.line_ids.mapped('calories'))
            rec.total_protein = sum(rec.line_ids.mapped('protein'))
            rec.total_fat = sum(rec.line_ids.mapped('fat'))
            rec.total_carbohydrate = sum(rec.line_ids.mapped('carbohydrate'))

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})


class L10nUaMealMenuLine(models.Model):
    _name = 'l10n_ua.meal.menu.line'
    _description = 'Страва в меню'
    _order = 'menu_id, meal_kind, sequence'

    menu_id = fields.Many2one('l10n_ua.meal.menu', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    meal_kind = fields.Selection([
        ('breakfast', 'Сніданок'),
        ('lunch', 'Обід'),
        ('afternoon', 'Полуденок'),
        ('dinner', 'Вечеря'),
        ('snack', 'Перекус'),
    ], string='Тип прийому', required=True, default='lunch')
    recipe_id = fields.Many2one('l10n_ua.meal.recipe', string='Страва', required=True)
    portion_grams = fields.Float(
        string='Порція, г',
        compute='_compute_recipe_data', store=True, readonly=False)
    calories = fields.Float(
        string='ккал', compute='_compute_recipe_data', store=True, readonly=False)
    protein = fields.Float(
        string='Б, г', compute='_compute_recipe_data', store=True, readonly=False)
    fat = fields.Float(
        string='Ж, г', compute='_compute_recipe_data', store=True, readonly=False)
    carbohydrate = fields.Float(
        string='В, г', compute='_compute_recipe_data', store=True, readonly=False)

    @api.depends('recipe_id')
    def _compute_recipe_data(self):
        for line in self:
            if line.recipe_id:
                line.portion_grams = line.recipe_id.yield_grams
                line.calories = line.recipe_id.calories_kcal
                line.protein = line.recipe_id.protein_g
                line.fat = line.recipe_id.fat_g
                line.carbohydrate = line.recipe_id.carbohydrate_g
