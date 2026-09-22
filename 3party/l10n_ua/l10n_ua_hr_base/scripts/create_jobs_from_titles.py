"""Створити довідник вакансій (hr.job) з текстових посад працівників.

Після імпорту бланків (наказів, Списків військового обліку) посада часто
лишається текстом у полі `job_title`, а штатної позиції у працівника немає.
Скрипт зводить такі тексти до канонічних назв, заводить відсутні вакансії і
проставляє їх працівникам.

Запуск:
    sudo -u odoo HOME=/tmp /opt/odoo/venv/bin/odoo shell \\
        -c /opt/odoo/odoo.conf -d <db> --no-http < create_jobs_from_titles.py

Змінні середовища:
    JOBS_APPLY — «1», щоб записати; без неї лише показує, що буде зроблено.
"""

import os
import re

APPLY = os.environ.get('JOBS_APPLY') == '1'

# Тексти з наказів — це не назви посад: наказ описує дію («Переведений на
# викладача»), а довідник потребує назви у називному відмінку. Відмінювання
# засобами коду не роблять — перелік коротший за будь-яку спробу вгадати
# правило, і кожен рядок тут видно й можна виправити.
ALIASES = {
    'викладач.': 'Викладач',
    'переведений на викладача': 'Викладач',
    'переведений на керівника фізвиховання': 'Керівник фізичного виховання',
    'переведений заступник директора з навчально-виробничої роботи':
        'Заступник директора з навчально-виробничої роботи',
    'переведений на заступника навчально-виробничої роботи':
        'Заступник директора з навчально-виробничої роботи',
    'переведений методист вищої категорії': 'Методист',
    'завідувач відділенням': 'Завідувач відділення',
}


def canonical(title):
    title = re.sub(r'\s+', ' ', (title or '')).strip().rstrip('.,;')
    if not title:
        return ''
    alias = ALIASES.get(title.lower())
    if alias:
        return alias
    return title[0].upper() + title[1:]


def main():
    Employee = env['hr.employee'].with_context(active_test=False)
    Job = env['hr.job']

    jobs = {job.name.strip().lower(): job for job in Job.search([])}
    employees = Employee.search([('job_id', '=', False)]).filtered('job_title')

    plan = {}
    for employee in employees:
        name = canonical(employee.job_title)
        if name:
            plan.setdefault(name, env['hr.employee'])
            plan[name] |= employee

    print('=== ВАКАНСІЇ З ТЕКСТОВИХ ПОСАД ===')
    created = 0
    for name in sorted(plan):
        staff = plan[name]
        job = jobs.get(name.lower())
        mark = 'існує' if job else 'СТВОРИТИ'
        print('%-9s %-55s осіб: %s' % (mark, name, len(staff)))
        if not job:
            created += 1
            if APPLY:
                job = Job.create({'name': name})
                jobs[name.lower()] = job
        if APPLY and job:
            # job_title ядро підставляє з вакансії саме при записі job_id,
            # тому окремо його вирівнювати не треба.
            staff.write({'job_id': job.id})

    print('---')
    print('різних посад:', len(plan), '| створити вакансій:', created,
          '| працівників:', sum(len(s) for s in plan.values()))
    print('режим:', 'ЗАПИС' if APPLY else 'сухий прогін (JOBS_APPLY=1 щоб записати)')
    if APPLY:
        env.cr.commit()
        print('зміни збережено')


main()
