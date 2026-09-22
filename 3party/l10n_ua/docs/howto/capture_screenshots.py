#!/usr/bin/env python3
"""Захоплення скріншотів HOWTO з демо-сервера через Playwright (headless Chromium).

Логіниться в Odoo й зберігає PNG у docs/howto/img/<домен>/ під іменами, на які
посилаються гайди. Працює без графічного дисплея (headless), тож придатне для CI.

Запуск:
    pip install playwright && playwright install chromium
    python3 capture_screenshots.py

Креденшали й адреса — через змінні середовища (дефолт — публічний демо-доступ):
    PW_BASE (https://demo.ndev.online), PW_LOGIN (demo), PW_PASSWORD (demo)

Примітка: action-ID (/odoo/action-NNN) специфічні для конкретної бази демо;
за потреби онови їх під свою інсталяцію.
"""
import os
from playwright.sync_api import sync_playwright

BASE = os.environ.get("PW_BASE", "https://demo.ndev.online")
LOGIN = os.environ.get("PW_LOGIN", "demo")
PASSWORD = os.environ.get("PW_PASSWORD", "demo")
IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")

# (домен, ім'я файлу, url, дія-над-сторінкою|None)
TARGETS = [
    ("hr", "01-employees-list.png", "/odoo/employees", None),
    ("hr", "12-payslips-list.png", "/odoo/action-454", None),
    ("hr", "05-payslip-form.png", "/odoo/action-454/121", None),
    ("hr", "06-payslip-accruals.png", "/odoo/action-454/121", ("tab", "Нарахування")),
    ("hr", "07-payslip-taxes.png", "/odoo/action-454/121", ("tab", "Податки та утримання")),
    ("accounting", "01-invoices.png", "/odoo/action-383", None),
    ("accounting", "03-assets-list.png", "/odoo/action-745", None),
    ("accounting", "04-asset-card.png", "/odoo/action-745/4", None),
    ("accounting", "05-depreciation-board.png", "/odoo/action-745/4", ("scroll", 900)),
    ("taxes", "02-vat-declaration.png", "/odoo/action-367", None),
    ("agreements", "03-agreement-states.png", "/odoo/action-838", None),
    ("education", "01-contingent.png", "/odoo/action-803", None),
    ("education", "02-scholarships.png", "/odoo/action-808", None),
]


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="uk-UA")
        page = ctx.new_page()
        page.goto(f"{BASE}/web/login", wait_until="domcontentloaded", timeout=45000)
        page.fill('input[name="login"]', LOGIN)
        page.fill('input[name="password"]', PASSWORD)
        page.press('input[name="password"]', "Enter")
        page.wait_for_url("**/odoo/**", timeout=45000)
        page.wait_for_timeout(2000)

        for domain, name, url, action in TARGETS:
            try:
                page.goto(f"{BASE}{url}", wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3500)
                if action and action[0] == "tab":
                    page.click(f'.o_notebook a.nav-link:has-text("{action[1]}")', timeout=8000)
                    page.wait_for_timeout(1200)
                elif action and action[0] == "scroll":
                    page.mouse.wheel(0, action[1])
                    page.wait_for_timeout(800)
                os.makedirs(os.path.join(IMG, domain), exist_ok=True)
                path = os.path.join(IMG, domain, name)
                page.screenshot(path=path)
                print("OK", os.path.relpath(path, IMG))
            except Exception as e:
                print("FAIL", domain, name, type(e).__name__, str(e)[:120])

        browser.close()


if __name__ == "__main__":
    run()
