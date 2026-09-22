"""Звести довідник вакансій за планом злиття.

Після імпорту кадрових списків у довіднику осідають варіанти написання однієї
посади («Черговий гурт. №1», «Черговий гуртожитку №1», «Черговий по гуртожитку
№2»). Скрипт виконує підготовлений план: переносить працівників на канонічну
вакансію, видаляє порожні дублікати, перейменовує скорочення й проставляє код
Класифікатора професій ДК 003:2010.

План — CSV із колонками:
    action  merge | rename | split
    source  наявна назва вакансії
    target  канонічна назва
    kp_code код КП-2010 для канонічної вакансії (необовʼязково)
    note    коментар (у роботі скрипта не використовується)

`split` не виконується автоматично: розділення суміщення (основна посада плюс
частка ставки) міняє умови оплати, тому такі рядки лише друкуються як перелік
для кадровика.

Запуск:
    sudo -u odoo HOME=/tmp JOBS_PLAN=/opt/odoo/import_data/job_merge_plan.csv \\
        /opt/odoo/venv/bin/odoo shell -c /opt/odoo/odoo.conf -d <db> --no-http \\
        < merge_jobs.py

Змінні середовища:
    JOBS_PLAN   — шлях до CSV-плану
    MERGE_APPLY — «1», щоб застосувати; без неї лише звіт
"""

import csv
import os
import re

PLAN_PATH = os.environ.get('JOBS_PLAN', '/opt/odoo/import_data/job_merge_plan.csv')
APPLY = os.environ.get('MERGE_APPLY') == '1'


def norm(text):
    return re.sub(r'\s+', ' ', (text or '')).strip().lower()


def main():
    Job = env['hr.job']
    Version = env['hr.version']
    Kp = env.get('hr.kp2010')

    jobs = {}
    for job in Job.search([]):
        jobs.setdefault(norm(job.name), job)

    with open(PLAN_PATH, encoding='utf-8') as handle:
        plan = list(csv.DictReader(handle))

    moved_total, removed, renamed, splits, problems = 0, [], [], [], []
    to_create = []

    for line in plan:
        action = (line['action'] or '').strip()
        source = jobs.get(norm(line['source']))
        target_name = (line['target'] or '').strip()
        kp_code = (line['kp_code'] or '').strip()

        if action == 'split':
            splits.append((line['source'], target_name, line['note']))
            continue

        if not source:
            problems.append('немає вакансії: %s' % line['source'])
            continue

        if action == 'rename':
            renamed.append((source.name, target_name))
            if APPLY:
                source.name = target_name
                _set_kp(source, kp_code, Kp, problems)
            continue

        # merge
        target = jobs.get(norm(target_name))
        if not target:
            # У сухому прогоні цільову вакансію не створюємо, але й не
            # замовкаємо: кадровику потрібні цифри переносу, а не сама лише
            # звістка, що вакансії ще немає.
            if APPLY:
                target = Job.create({'name': target_name})
                jobs[norm(target_name)] = target
            elif target_name not in to_create:
                to_create.append(target_name)
        if target and target == source:
            continue

        versions = Version.search([('job_id', '=', source.id)])
        moved_total += len(versions)
        print('  %-52s → %-34s осіб: %s' % (
            source.name[:52], target_name[:34], len(versions)))
        if not target:
            continue
        if APPLY:
            versions.write({'job_id': target.id})
            _set_kp(target, kp_code, Kp, problems)
            removed.append(source.name)
            source.unlink()

    print('=== ПЛАН ЗЛИТТЯ ВАКАНСІЙ ===')
    print('перенесено працівників:', moved_total)
    print('видалено дублікатів:   ', len(removed))
    if renamed:
        print('перейменовано:')
        for old, new in renamed:
            print('   %-46s → %s' % (old[:46], new))
    if splits:
        print('суміщення — розділити вручну (%s):' % len(splits))
        for source, target, note in splits:
            print('   %-44s основна: %-24s %s' % (source[:44], target[:24], note))
    if to_create:
        print('буде створено канонічних вакансій:', len(to_create))
        for name in to_create:
            print('   +', name)
    if problems:
        print('увага:')
        for problem in problems:
            print('   !', problem)
    print('вакансій у довіднику:', Job.search_count([]))
    print('режим:', 'ЗАПИС' if APPLY else 'сухий прогін (MERGE_APPLY=1 щоб виконати)')
    if APPLY:
        env.cr.commit()
        print('зміни збережено')


def _set_kp(job, kp_code, Kp, problems):
    """Проставити код Класифікатора професій, якщо модель це підтримує."""
    if not kp_code or Kp is None or 'kp_id' not in job._fields:
        return
    kp = Kp.search([('code', '=', kp_code)], limit=1)
    if kp:
        job.kp_id = kp.id
    else:
        problems.append('немає коду КП %s для %s' % (kp_code, job.name))


main()
