"""Chart template for Ukrainian public sector — Наказ Мінфіну № 1203 від 31.12.2013.

Завантажується через `account.chart_template` API в Odoo 19. Базові коди
відображають субʼєкта сектору «розпорядник бюджетних коштів» (третя цифра = 1).
"""
from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ua_state')
    def _get_ua_state_template_data(self):
        return {
            'name': 'Україна — бухоблік у державному секторі (Наказ № 1203)',
            'code_digits': '4',
            'property_account_receivable_id': 'ua_state_2117',
            'property_account_payable_id': 'ua_state_6614',
            'property_account_expense_categ_id': 'ua_state_8013',
            'property_account_income_categ_id': 'ua_state_7411',
        }

    @template('ua_state', 'res.company')
    def _get_ua_state_res_company(self):
        return {
            self.env.company.id: {
                'account_fiscal_country_id': 'base.ua',
                'bank_account_code_prefix': '2313',
                'cash_account_code_prefix': '2411',
                'transfer_account_code_prefix': '2215',
                'income_currency_exchange_account_id': 'ua_state_7411',
                'expense_currency_exchange_account_id': 'ua_state_8411',
            },
        }

    @template('ua_state', 'account.journal')
    def _get_ua_state_account_journal(self):
        return {
            'bank': {'name': 'Реєстраційний рахунок (ДКСУ)', 'type': 'bank', 'code': 'РЕЄ', 'sequence': 5},
            'cash': {'name': 'Каса', 'type': 'cash', 'code': 'КАСА', 'sequence': 10},
            'general': {'name': 'Загальний журнал', 'type': 'general', 'code': 'STJ', 'show_on_dashboard': True},
            'sale': {'name': 'Доходи від платних послуг', 'type': 'sale', 'code': 'ВИКЛ', 'sequence': 20},
            'purchase': {'name': 'Закупівлі', 'type': 'purchase', 'code': 'ЗАКУП', 'sequence': 30},
        }

    @template('ua_state', 'account.account')
    def _get_ua_state_account_account(self):
        """Plan of Accounts for the public sector (Наказ № 1203).

        Identifiers `ua_state_NNNN` map to 4-digit subaccount codes. All
        accounts get `ua_budget_is_state_sector=True` so that the budget
        module's analytic helpers know they belong to this chart.
        """
        # Helper to keep the dict compact
        def acc(code, name, atype):
            return {
                'name': name, 'code': code, 'account_type': atype,
                'ua_budget_is_state_sector': True,
            }

        return {
            # ============================================================
            # Class 1 — Necurrent assets (10xx-15xx)
            # ============================================================
            'ua_state_1011': acc('1011', 'Земельні ділянки', 'asset_non_current'),
            'ua_state_1012': acc('1012', 'Капітальні витрати на поліпшення земель', 'asset_non_current'),
            'ua_state_1013': acc('1013', 'Будівлі, споруди та передавальні пристрої', 'asset_non_current'),
            'ua_state_1014': acc('1014', 'Машини та обладнання', 'asset_non_current'),
            'ua_state_1015': acc('1015', 'Транспортні засоби', 'asset_non_current'),
            'ua_state_1016': acc('1016', 'Інструменти, прилади, інвентар', 'asset_non_current'),
            'ua_state_1017': acc('1017', 'Тварини та багаторічні насадження', 'asset_non_current'),
            'ua_state_1018': acc('1018', 'Інші основні засоби', 'asset_non_current'),
            'ua_state_1111': acc('1111', 'Музейні фонди', 'asset_non_current'),
            'ua_state_1112': acc('1112', 'Бібліотечні фонди', 'asset_non_current'),
            'ua_state_1113': acc('1113', 'Малоцінні необоротні матеріальні активи', 'asset_non_current'),
            'ua_state_1114': acc('1114', "Білизна, постільні речі, одяг та взуття", 'asset_non_current'),
            'ua_state_1115': acc('1115', 'Інвентарна тара', 'asset_non_current'),
            'ua_state_1116': acc('1116', 'Необоротні матеріальні активи спеціального призначення', 'asset_non_current'),
            'ua_state_1117': acc('1117', 'Природні ресурси', 'asset_non_current'),
            'ua_state_1118': acc('1118', 'Інші необоротні матеріальні активи', 'asset_non_current'),
            'ua_state_1211': acc('1211', 'Авторське та суміжні з ним права', 'asset_non_current'),
            'ua_state_1212': acc('1212', 'Права користування природними ресурсами', 'asset_non_current'),
            'ua_state_1213': acc('1213', 'Права на знаки для товарів і послуг', 'asset_non_current'),
            'ua_state_1214': acc('1214', 'Права користування майном', 'asset_non_current'),
            'ua_state_1215': acc('1215', 'Права на об\'єкти промислової власності', 'asset_non_current'),
            'ua_state_1216': acc('1216', 'Інші нематеріальні активи', 'asset_non_current'),
            'ua_state_1311': acc('1311', 'Капітальні інвестиції в основні засоби', 'asset_non_current'),
            'ua_state_1312': acc('1312', 'Капітальні інвестиції в інші необоротні матеріальні активи', 'asset_non_current'),
            'ua_state_1313': acc('1313', 'Капітальні інвестиції в нематеріальні активи', 'asset_non_current'),
            'ua_state_1314': acc('1314', 'Капітальні інвестиції в незавершене будівництво', 'asset_non_current'),
            'ua_state_1411': acc('1411', 'Знос основних засобів', 'asset_non_current'),
            'ua_state_1412': acc('1412', 'Знос інших необоротних матеріальних активів', 'asset_non_current'),
            'ua_state_1413': acc('1413', 'Накопичена амортизація нематеріальних активів', 'asset_non_current'),
            'ua_state_1511': acc('1511', 'Довгострокові біологічні активи рослинництва', 'asset_non_current'),
            'ua_state_1512': acc('1512', 'Довгострокові біологічні активи тваринництва', 'asset_non_current'),
            'ua_state_1513': acc('1513', 'Накопичена амортизація довгострокових біологічних активів', 'asset_non_current'),

            # ============================================================
            # Class 2 — Financial assets / inventories (18xx, 20xx-25xx)
            # ============================================================
            'ua_state_1811': acc('1811', 'Готова продукція', 'asset_current'),
            'ua_state_1812': acc('1812', 'Малоцінні та швидкозношувані предмети', 'asset_current'),
            'ua_state_2011': acc('2011', 'Сировина і матеріали', 'asset_current'),
            'ua_state_2012': acc('2012', 'Обладнання, конструкції і деталі до установки', 'asset_current'),
            'ua_state_2013': acc('2013', 'Спецобладнання для науково-дослідних робіт', 'asset_current'),
            'ua_state_2014': acc('2014', 'Будівельні матеріали', 'asset_current'),
            'ua_state_2015': acc('2015', 'Інші виробничі запаси', 'asset_current'),
            'ua_state_2111': acc('2111', 'Поточна дебіторська заборгованість за товари, роботи, послуги', 'asset_receivable'),
            'ua_state_2112': acc('2112', 'Дебіторська заборгованість за розрахунками з бюджетом', 'asset_receivable'),
            'ua_state_2113': acc('2113', 'Розрахунки за авансами, виданими постачальникам', 'asset_receivable'),
            'ua_state_2114': acc('2114', 'Дебіторська заборгованість за розрахунками із соцстрахування', 'asset_receivable'),
            'ua_state_2115': acc('2115', 'Розрахунки з відшкодування завданих збитків', 'asset_receivable'),
            'ua_state_2116': acc('2116', 'Дебіторська заборгованість із внутрішніх розрахунків', 'asset_receivable'),
            'ua_state_2117': acc('2117', 'Інша поточна дебіторська заборгованість', 'asset_receivable'),
            'ua_state_2118': acc('2118', 'Розрахунки за спільною діяльністю', 'asset_receivable'),
            'ua_state_2211': acc('2211', 'Грошові кошти в національній валюті', 'asset_cash'),
            'ua_state_2212': acc('2212', 'Грошові кошти в іноземній валюті', 'asset_cash'),
            'ua_state_2213': acc('2213', 'Грошові документи в національній валюті', 'asset_cash'),
            'ua_state_2214': acc('2214', 'Грошові документи в іноземній валюті', 'asset_cash'),
            'ua_state_2215': acc('2215', 'Грошові кошти в дорозі в національній валюті', 'asset_cash'),
            'ua_state_2216': acc('2216', 'Грошові кошти в дорозі в іноземній валюті', 'asset_cash'),
            'ua_state_2311': acc('2311', 'Поточні рахунки в банку', 'asset_cash'),
            'ua_state_2313': acc('2313', 'Реєстраційні рахунки', 'asset_cash'),
            'ua_state_2314': acc('2314', 'Інші рахунки в Казначействі', 'asset_cash'),
            'ua_state_2411': acc('2411', 'Каса в національній валюті', 'asset_cash'),
            'ua_state_2412': acc('2412', 'Каса в іноземній валюті', 'asset_cash'),
            'ua_state_2511': acc('2511', 'Фінансові інвестиції (поточні)', 'asset_current'),

            # ============================================================
            # Class 5 — Capital + financial result (51-55)
            # ============================================================
            'ua_state_5111': acc('5111', 'Внесений капітал розпорядникам бюджетних коштів', 'equity'),
            'ua_state_5311': acc('5311', 'Капітал у дооцінках', 'equity'),
            'ua_state_5411': acc('5411', 'Цільове фінансування розпорядників бюджетних коштів', 'equity'),
            'ua_state_5511': acc('5511', 'Фінансові результати виконання кошторису звітного періоду', 'equity'),
            'ua_state_5512': acc('5512', 'Накопичені фінансові результати виконання кошторису', 'equity'),

            # ============================================================
            # Class 6 — Liabilities (60-67)
            # ============================================================
            'ua_state_6011': acc('6011', 'Короткострокові позики в національній валюті', 'liability_current'),
            'ua_state_6012': acc('6012', 'Короткострокові позики в іноземній валюті', 'liability_current'),
            'ua_state_6111': acc('6111', 'Поточна заборгованість за довгостроковими зобов\'язаннями (нац.вал.)', 'liability_current'),
            'ua_state_6112': acc('6112', 'Поточна заборгованість за довгостроковими зобов\'язаннями (інозем.вал.)', 'liability_current'),
            'ua_state_6211': acc('6211', 'Розрахунки з постачальниками та підрядниками', 'liability_payable'),
            'ua_state_6212': acc('6212', 'Розрахунки із замовниками за роботи і послуги', 'liability_payable'),
            'ua_state_6311': acc('6311', 'Розрахунки з бюджетом за податками і зборами', 'liability_current'),
            'ua_state_6312': acc('6312', 'Інші розрахунки з бюджетом', 'liability_current'),
            'ua_state_6313': acc('6313', "Розрахунки із загальнообов'язкового державного соцстрахування", 'liability_current'),
            'ua_state_6411': acc('6411', 'Розрахунки за коштами, тимчасово віднесеними на доходи держбюджету', 'liability_current'),
            'ua_state_6412': acc('6412', 'Розрахунки за коштами, тимчасово віднесеними на доходи місцевого бюджету', 'liability_current'),
            'ua_state_6511': acc('6511', 'Розрахунки із заробітної плати', 'liability_current'),
            'ua_state_6512': acc('6512', 'Розрахунки за виплатами працівникам', 'liability_current'),
            'ua_state_6513': acc('6513', 'Розрахунки з працівниками за товари, продані в кредит', 'liability_current'),
            'ua_state_6514': acc('6514', 'Розрахунки із депонентами', 'liability_current'),
            'ua_state_6515': acc('6515', 'Розрахунки з працівниками за безготівковими перерахуваннями на рахунки з вкладів у банках', 'liability_current'),
            'ua_state_6516': acc('6516', 'Розрахунки з працівниками за безготівковими перерахуваннями внесків добровільного страхування', 'liability_current'),
            'ua_state_6517': acc('6517', 'Розрахунки з членами профспілки безготівковими перерахуваннями членських внесків', 'liability_current'),
            'ua_state_6518': acc('6518', "Розрахунки із суб'єктами обов'язкового відрахування", 'liability_current'),
            'ua_state_6611': acc('6611', 'Розрахунки з підзвітними особами', 'liability_current'),
            'ua_state_6612': acc('6612', 'Розрахунки за відшкодування завданих збитків', 'liability_current'),
            'ua_state_6613': acc('6613', 'Розрахунки за спеціальними видами платежів', 'liability_current'),
            'ua_state_6614': acc('6614', 'Розрахунки з іншими кредиторами', 'liability_payable'),
            'ua_state_6711': acc('6711', 'Внутрішні розрахунки за операціями з внутрішнього переміщення активів і зобов\'язань', 'liability_current'),

            # ============================================================
            # Class 7 — Income (70-75)
            # ============================================================
            'ua_state_7011': acc('7011', 'Бюджетні асигнування', 'income'),
            'ua_state_7111': acc('7111', 'Доходи від реалізації продукції (робіт, послуг)', 'income'),
            'ua_state_7211': acc('7211', 'Дохід від реалізації активів', 'income'),
            'ua_state_7311': acc('7311', 'Фінансові доходи розпорядників бюджетних коштів', 'income'),
            'ua_state_7411': acc('7411', "Інші доходи за обмінними операціями", 'income_other'),
            'ua_state_7511': acc('7511', 'Доходи за необмінними операціями', 'income_other'),
            'ua_state_7512': acc('7512', 'Трансферти', 'income_other'),
            'ua_state_7513': acc('7513', 'Гранти, дарунки', 'income_other'),

            # ============================================================
            # Class 8 — Expenses (80-85)
            # ============================================================
            'ua_state_8011': acc('8011', 'Витрати на оплату праці', 'expense'),
            'ua_state_8012': acc('8012', 'Відрахування на соціальні заходи', 'expense'),
            'ua_state_8013': acc('8013', 'Матеріальні витрати', 'expense'),
            'ua_state_8014': acc('8014', 'Амортизація', 'expense_depreciation'),
            'ua_state_8111': acc('8111', 'Витрати на оплату праці (розпорядники)', 'expense'),
            'ua_state_8112': acc('8112', 'Відрахування на соціальні заходи (розпорядники)', 'expense'),
            'ua_state_8113': acc('8113', 'Матеріальні витрати (розпорядники)', 'expense'),
            'ua_state_8114': acc('8114', 'Амортизація (розпорядники)', 'expense_depreciation'),
            'ua_state_8115': acc('8115', 'Інші витрати', 'expense'),
            'ua_state_8211': acc('8211', 'Собівартість реалізованих активів', 'expense_direct_cost'),
            'ua_state_8212': acc('8212', "Витрати, пов'язані з реалізацією майна", 'expense'),
            'ua_state_8311': acc('8311', 'Фінансові витрати', 'expense'),
            'ua_state_8411': acc('8411', 'Інші витрати за обмінними операціями', 'expense'),
            'ua_state_8511': acc('8511', "Витрати за необмінними операціями", 'expense'),
            'ua_state_8512': acc('8512', 'Трансферти (видатки)', 'expense'),
            'ua_state_8513': acc('8513', 'Гранти, дарунки (видатки)', 'expense'),

            # ============================================================
            # Class 0 — Off-balance (01-09)
            # ============================================================
            'ua_state_01': acc('0001', 'Орендовані основні засоби', 'off_balance'),
            'ua_state_02': acc('0002', 'Активи на відповідальному зберіганні', 'off_balance'),
            'ua_state_03': acc('0003', 'Бланки документів суворого обліку', 'off_balance'),
            'ua_state_04': acc('0004', "Непередбачені активи і зобов'язання", 'off_balance'),
            'ua_state_05': acc('0005', 'Гарантії та забезпечення надані', 'off_balance'),
            'ua_state_06': acc('0006', 'Гарантії та забезпечення отримані', 'off_balance'),
            'ua_state_07': acc('0007', 'Списані активи', 'off_balance'),
            'ua_state_08': acc('0008', "Бюджетні зобов'язання", 'off_balance'),
            'ua_state_09': acc('0009', "Призначення та зобов'язання за фондом", 'off_balance'),
        }
