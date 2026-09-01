import base64

from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestImportProfileSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({"name": "Import Other Company"})
        cls.vendor = cls.env["res.partner"].create({
            "name": "Profile Test Vendor",
            "supplier_rank": 1,
        })
        cls.purchase_user = new_test_user(
            cls.env,
            login="purchase_import_user",
            groups="purchase.group_purchase_user",
            company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id])],
        )
        cls.purchase_manager = new_test_user(
            cls.env,
            login="purchase_import_profile_manager",
            groups="purchase.group_purchase_manager",
            company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id])],
        )

    def _profile_values(self, name, company=None):
        return {
            "name": name,
            "company_id": (company or self.company).id,
            "mapping_ids": [
                Command.create({"source_column": "Code", "target": "default_code"}),
                Command.create({"source_column": "Qty", "target": "quantity"}),
                Command.create({"source_column": "Price", "target": "price"}),
            ],
        }

    def test_profile_constraints_copy_and_manager_access(self):
        Profile = self.env["purchase.import.profile"]
        profile = Profile.with_user(self.purchase_manager).create(
            self._profile_values("Managed Profile")
        )
        self.assertEqual(profile.lookup_ids.mapped("lookup_type"), [
            "supplier_code", "default_code", "barcode"
        ])
        with self.assertRaises(AccessError):
            Profile.with_user(self.purchase_user).create(self._profile_values("Forbidden"))
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                Profile.create(self._profile_values("Managed Profile"))
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                Profile.create({
                    **self._profile_values("Bad Rows"),
                    "header_row": 2,
                    "data_row": 2,
                })
        with self.assertRaises(ValidationError):
            profile.mapping_ids.create({
                "profile_id": profile.id,
                "source_column": "Other Code",
                "target": "default_code",
            })

        order = self.env["purchase.order"].create({
            "partner_id": self.vendor.id,
            "company_id": self.company.id,
        })
        wizard = self.env["purchase.order.line.import.wizard"].with_user(
            self.purchase_manager
        ).create({
            "order_id": order.id,
            "profile_id": profile.id,
            "file_data": base64.b64encode(b"Code,Qty,Price\nUNKNOWN,1,2\n"),
            "file_name": "purchase.csv",
        })
        wizard._onchange_profile_id()
        wizard.action_parse()
        self.assertEqual(
            wizard.mapping_ids.filtered("target").mapped("target"),
            ["default_code", "quantity", "price"],
        )
        wizard.profile_name = "Copied Profile"
        wizard.action_save_profile()
        copied = wizard.profile_id
        self.assertEqual(copied.name, "Copied Profile")
        self.assertEqual(copied.mapping_ids.mapped("source_column"), ["Code", "Qty", "Price"])

    def test_profile_mapping_readonly_source_columns_are_saved(self):
        profile = self.env["purchase.import.profile"].create(
            self._profile_values("Readonly Mapping Profile")
        )
        order = self.env["purchase.order"].create({
            "partner_id": self.vendor.id,
            "company_id": self.company.id,
        })

        wizard_form = Form(
            self.env["purchase.order.line.import.wizard"].with_context(
                default_order_id=order.id,
                default_file_name="purchase.csv",
            ),
            view="purchase_import.purchase_order_line_import_wizard_view_form",
        )
        wizard_form.profile_id = profile
        wizard_form.file_data = base64.b64encode(b"Code,Qty,Price\nUNKNOWN,1,2\n")
        wizard = wizard_form.save()

        self.assertEqual(
            wizard.mapping_ids.mapped("source_column"), ["Code", "Qty", "Price"]
        )

    def test_company_rule_and_cross_company_wizard_guard(self):
        profile = self.env["purchase.import.profile"].create(
            self._profile_values("Other Company Profile", self.other_company)
        )
        visible = self.env["purchase.import.profile"].with_user(self.purchase_manager).search([
            ("id", "=", profile.id)
        ])
        self.assertFalse(visible)
        with self.assertRaises(AccessError):
            profile.with_user(self.purchase_manager).read(["name"])

        order = self.env["purchase.order"].create({
            "partner_id": self.vendor.id,
            "company_id": self.company.id,
        })
        with self.assertRaises(UserError):
            self.env["purchase.order.line.import.wizard"].with_user(
                self.purchase_manager
            ).create({
                "order_id": order.id,
                "profile_id": profile.id,
                "file_data": base64.b64encode(b"Code,Qty,Price\nX,1,2\n"),
                "file_name": "purchase.csv",
            })

    def test_lifecycle_and_product_creation_permission(self):
        product = self.env["product.product"].create({
            "name": "Lifecycle Product",
            "purchase_ok": True,
            "company_id": self.company.id,
        })
        order = self.env["purchase.order"].create({
            "partner_id": self.vendor.id,
            "company_id": self.company.id,
            "order_line": [Command.create({
                "product_id": product.id,
                "product_qty": 1,
                "product_uom_id": product.uom_id.id,
                "price_unit": 1,
            })],
        })
        order.button_confirm()
        with self.assertRaisesRegex(UserError, "unlocked draft"):
            order.action_open_line_import()

        draft = self.env["purchase.order"].create({
            "partner_id": self.vendor.id,
            "company_id": self.company.id,
        })
        wizard = self.env["purchase.order.line.import.wizard"].with_user(
            self.purchase_manager
        ).create({
            "order_id": draft.id,
            "file_data": base64.b64encode(b"Name,Qty,Price\nNo Access Product,1,2\n"),
            "file_name": "purchase.csv",
            "unmatched_policy": "create",
            "creation_mode": "standalone",
        })
        wizard.action_parse()
        targets = {"Name": "product_name", "Qty": "quantity", "Price": "price"}
        for mapping in wizard.mapping_ids:
            mapping.target = targets[mapping.source_column]
        wizard.action_preview()
        self.assertFalse(wizard.preview_valid)
        self.assertIn("permission to create", wizard.preview_ids.error_message)
