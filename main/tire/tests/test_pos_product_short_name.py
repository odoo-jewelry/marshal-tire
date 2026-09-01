from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPosProductShortName(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config = cls.env["pos.config"].create({
            "name": "POS Product Short Name Test",
        })
        cls.product = cls.env["product.template"].create({
            "name": "Full Product Name",
            "available_in_pos": True,
            "pos_short_name": "Short Name",
        })

    def test_pos_short_name_is_loaded_without_replacing_name(self):
        fields_to_load = self.product._load_pos_data_fields(self.pos_config)
        self.assertIn("pos_short_name", fields_to_load)

        [product_data] = self.product._load_pos_data_read(self.product, self.pos_config)
        self.assertEqual(product_data["pos_short_name"], "Short Name")
        self.assertEqual(product_data["name"], "Full Product Name")

        self.product.pos_short_name = False
        [product_data] = self.product._load_pos_data_read(self.product, self.pos_config)
        self.assertFalse(product_data["pos_short_name"])
        self.assertEqual(product_data["name"], "Full Product Name")
