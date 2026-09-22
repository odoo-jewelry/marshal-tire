"""Unit tests для tools.json_path."""

from odoo.tests import TransactionCase, tagged

from ..tools.json_path import parse_path, resolve, resolve_first


@tagged('post_install', '-at_install')
class TestJsonPath(TransactionCase):

    def test_parse_path_simple_key(self):
        self.assertEqual(parse_path('name'), [('key', 'name')])

    def test_parse_path_dotted(self):
        self.assertEqual(parse_path('a.b.c'),
                         [('key', 'a'), ('key', 'b'), ('key', 'c')])

    def test_parse_path_index(self):
        self.assertEqual(parse_path('items[0]'),
                         [('key', 'items'), ('index', 0)])

    def test_parse_path_iter(self):
        self.assertEqual(parse_path('items[*]'),
                         [('key', 'items'), ('iter', '*')])

    def test_parse_path_complex(self):
        self.assertEqual(parse_path('a.b[*].c[0].d'), [
            ('key', 'a'), ('key', 'b'), ('iter', '*'),
            ('key', 'c'), ('index', 0), ('key', 'd'),
        ])

    def test_parse_path_empty(self):
        self.assertEqual(parse_path(''), [])

    def test_resolve_simple_key(self):
        self.assertEqual(resolve({'name': 'foo'}, 'name'), ['foo'])

    def test_resolve_dotted(self):
        data = {'a': {'b': {'c': 42}}}
        self.assertEqual(resolve(data, 'a.b.c'), [42])

    def test_resolve_index(self):
        data = {'items': ['a', 'b', 'c']}
        self.assertEqual(resolve(data, 'items[0]'), ['a'])
        self.assertEqual(resolve(data, 'items[2]'), ['c'])

    def test_resolve_negative_index(self):
        data = {'items': ['a', 'b', 'c']}
        self.assertEqual(resolve(data, 'items[-1]'), ['c'])

    def test_resolve_iter(self):
        data = {'items': [{'p': 1}, {'p': 2}, {'p': 3}]}
        self.assertEqual(resolve(data, 'items[*].p'), [1, 2, 3])

    def test_resolve_missing_key_returns_empty(self):
        self.assertEqual(resolve({'a': 1}, 'b'), [])

    def test_resolve_missing_nested_returns_empty(self):
        self.assertEqual(resolve({'a': {}}, 'a.b.c'), [])

    def test_resolve_index_out_of_range(self):
        self.assertEqual(resolve({'items': ['a']}, 'items[5]'), [])

    def test_resolve_iter_on_non_list(self):
        # ітерація по dict — нічого не повертає
        self.assertEqual(resolve({'a': {'b': 1}}, 'a[*]'), [])

    def test_resolve_first_default(self):
        self.assertIsNone(resolve_first({}, 'missing'))
        self.assertEqual(resolve_first({}, 'missing', default='X'), 'X')

    def test_resolve_first_found(self):
        self.assertEqual(resolve_first({'name': 'foo'}, 'name'), 'foo')
