"""Reusable service for budget limit validation.

ПКМУ № 938 від 28.10.2015 і Бюджетний кодекс ст. 48 вимагають, щоб
розпорядники бюджетних коштів не приймали зобов'язань і не здійснювали
платежів понад затверджені кошторисом асигнування.

Цей модуль інкапсулює перевірку, щоб і `account.move`, і майбутні
зобов'язання (`account.payment` через payment_term) могли її використовувати.
"""
from collections import defaultdict
from odoo import models, _
from odoo.exceptions import UserError


class BudgetLimitChecker(models.AbstractModel):
    _name = 'l10n_ua.budget.limit.checker'
    _description = 'Перевірка ліміту бюджетних асигнувань'

    @staticmethod
    def _bucket_key(line):
        """Group key for limit aggregation: (year, КЕКВ, фонд, КПКВК).

        КПКВК є опційним полем у проводці — None означає «без прив'язки до програми»,
        що теж є валідним bucket (для деяких рахунків).
        """
        year = line.date.year if line.date else None
        return (
            year,
            line.ua_kekv_id.id,
            line.ua_fund_type,
            line.ua_kpkvk_id.id if line.ua_kpkvk_id else None,
        )

    def check_move_against_limits(self, move):
        """Verify that posting `move` won't exceed approved-estimate allocations.

        Сумуємо `debit` по всіх рядках проводки, які мають заповнені КЕКВ + фонд,
        групуємо по (рік, КЕКВ, фонд, КПКВК) і порівнюємо з затвердженим планом.

        Кидаємо UserError, якщо хоча б один bucket перевищує ліміт.
        """
        if move.move_type != 'entry' and move.state == 'posted':
            return  # already posted invoice paths handled separately

        buckets = defaultdict(float)
        for line in move.line_ids:
            if not line.ua_kekv_id or not line.ua_fund_type or not line.date:
                continue
            buckets[self._bucket_key(line)] += line.debit

        if not buckets:
            return

        Estimate = self.env['l10n_ua.budget.estimate.line']
        violations = []
        for (year, kekv_id, fund, kpkvk_id), debit in buckets.items():
            if not debit:
                continue
            domain = [
                ('year', '=', year),
                ('kekv_id', '=', kekv_id),
                ('fund_type', '=', fund),
                ('state', 'in', ('approved', 'executed')),
                ('company_id', '=', move.company_id.id),
            ]
            if kpkvk_id:
                domain.append(('kpkvk_id', '=', kpkvk_id))
            else:
                domain.append(('kpkvk_id', '=', False))

            est_lines = Estimate.search(domain)
            if not est_lines:
                violations.append({
                    'kind': 'missing_estimate',
                    'year': year, 'kekv_id': kekv_id, 'fund': fund, 'kpkvk_id': kpkvk_id,
                    'amount': debit,
                })
                continue

            # Use existing computed amount_actual + this new debit.
            planned = sum(est_lines.mapped('amount_planned'))
            already_used = sum(est_lines.mapped('amount_actual'))
            available = planned - already_used
            if debit > available + 0.005:  # small float tolerance
                violations.append({
                    'kind': 'over_limit',
                    'year': year, 'kekv_id': kekv_id, 'fund': fund, 'kpkvk_id': kpkvk_id,
                    'amount': debit, 'planned': planned,
                    'used': already_used, 'available': available,
                    'estimate_lines': est_lines,
                })

        if violations:
            self._raise_for_violations(violations)

    def _raise_for_violations(self, violations):
        """Build a single UserError with all violations rolled up."""
        Kekv = self.env['l10n_ua.kekv']
        msgs = []
        for v in violations:
            kekv = Kekv.browse(v['kekv_id'])
            fund_label = {'general': 'заг. фонд', 'special': 'спец. фонд'}.get(v['fund'], v['fund'])
            if v['kind'] == 'missing_estimate':
                msgs.append(_(
                    'Немає затвердженого кошторису для %(year)s, КЕКВ %(kekv)s (%(fund)s), '
                    'сума %(amt).2f. Затвердьте кошторис або вкажіть інший КЕКВ.',
                    year=v['year'], kekv=kekv.code or '?',
                    fund=fund_label, amt=v['amount']))
            else:
                msgs.append(_(
                    'Перевищення ліміту по %(year)s, КЕКВ %(kekv)s (%(fund)s): '
                    'спроба провести %(amt).2f, залишок %(avail).2f '
                    '(план %(plan).2f, факт %(used).2f).',
                    year=v['year'], kekv=kekv.code or '?', fund=fund_label,
                    amt=v['amount'], avail=v['available'],
                    plan=v['planned'], used=v['used']))
        raise UserError('\n\n'.join(msgs))
