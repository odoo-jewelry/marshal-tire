"""Тести SFTP fetcher. paramiko мокований."""

import base64
import io
import json
from unittest.mock import patch, MagicMock

import paramiko

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSftpFetcher(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'SFTP Supplier', 'supplier_rank': 1,
        })
        cls.uah = cls.env.ref('base.UAH')
        cls.mapping = cls.env['l10n_ua.supplier.price.mapping'].create({
            'name': 'SFTP Test',
            'record_path': 'items',
            'field_ids': [
                (0, 0, {'target': 'sku', 'source_path': 'code', 'required': True}),
                (0, 0, {'target': 'price', 'source_path': 'price', 'required': True,
                        'transform': 'to_float'}),
            ],
        })

    def _make_source(self, connection_config):
        return self.env['l10n_ua.supplier.price.source'].create({
            'name': 'SFTP Source',
            'partner_id': self.partner.id,
            'fetcher_type': 'sftp',
            'parser_type': 'json',
            'mapping_id': self.mapping.id,
            'currency_default_id': self.uah.id,
            'connection_config': json.dumps(connection_config),
        })

    def _make_import(self, source):
        return self.env['l10n_ua.supplier.price.import'].create({'source_id': source.id})

    def _make_mock_sshclient(self, file_content=b''):
        """Створити mock SSHClient з sftp.open() що повертає buffer."""
        mock_client = MagicMock()
        mock_sftp = MagicMock()
        # sftp.open() returns context manager-like object
        mock_file = MagicMock()
        mock_file.read.return_value = file_content
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_sftp.open.return_value = mock_file
        mock_client.open_sftp.return_value = mock_sftp
        return mock_client, mock_sftp

    @patch('paramiko.SSHClient')
    def test_fetch_with_password(self, MockSSHClient):
        mock_client, mock_sftp = self._make_mock_sshclient(b'{"items":[{"code":"X","price":"10"}]}')
        MockSSHClient.return_value = mock_client
        source = self._make_source({
            'host': 'sftp.example.com',
            'username': 'user',
            'password': 'pass',
            'remote_path': '/exports/prices.json',
        })
        imp = self._make_import(source)
        imp.action_fetch()
        self.assertEqual(imp.state, 'fetched')
        self.assertEqual(imp.raw_filename, 'prices.json')
        # connect called with password
        mock_client.connect.assert_called_once()
        kwargs = mock_client.connect.call_args.kwargs
        self.assertEqual(kwargs['password'], 'pass')
        self.assertEqual(kwargs['hostname'], 'sftp.example.com')
        self.assertEqual(kwargs['port'], 22)
        # cleanup called
        mock_client.close.assert_called_once()

    @patch('paramiko.SSHClient')
    def test_fetch_with_key_file(self, MockSSHClient):
        mock_client, _sftp = self._make_mock_sshclient(b'data')
        MockSSHClient.return_value = mock_client
        source = self._make_source({
            'host': 'h', 'username': 'u',
            'key_file': '/tmp/key.pem',
            'remote_path': '/p.csv',
        })
        imp = self._make_import(source)
        imp.action_fetch()
        kwargs = mock_client.connect.call_args.kwargs
        self.assertEqual(kwargs['key_filename'], '/tmp/key.pem')
        self.assertNotIn('password', kwargs)

    @patch('paramiko.SSHClient')
    def test_fetch_custom_port(self, MockSSHClient):
        mock_client, _sftp = self._make_mock_sshclient(b'data')
        MockSSHClient.return_value = mock_client
        source = self._make_source({
            'host': 'h', 'port': 2222, 'username': 'u', 'password': 'p',
            'remote_path': '/p',
        })
        imp = self._make_import(source)
        imp.action_fetch()
        kwargs = mock_client.connect.call_args.kwargs
        self.assertEqual(kwargs['port'], 2222)

    @patch('paramiko.SSHClient')
    def test_fetch_authentication_error(self, MockSSHClient):
        mock_client = MagicMock()
        mock_client.connect.side_effect = paramiko.AuthenticationException("bad creds")
        MockSSHClient.return_value = mock_client
        source = self._make_source({
            'host': 'h', 'username': 'u', 'password': 'wrong', 'remote_path': '/p',
        })
        imp = self._make_import(source)
        imp.action_fetch()
        self.assertEqual(imp.state, 'error')
        self.assertIn('authentication failed', imp.error_log.lower())

    @patch('paramiko.SSHClient')
    def test_fetch_connection_error(self, MockSSHClient):
        mock_client = MagicMock()
        mock_client.connect.side_effect = OSError("connection refused")
        MockSSHClient.return_value = mock_client
        source = self._make_source({
            'host': 'h', 'username': 'u', 'password': 'p', 'remote_path': '/p',
        })
        imp = self._make_import(source)
        imp.action_fetch()
        self.assertEqual(imp.state, 'error')
        self.assertIn('connection failed', imp.error_log.lower())

    @patch('paramiko.SSHClient')
    def test_fetch_remote_file_not_found(self, MockSSHClient):
        mock_client = MagicMock()
        mock_sftp = MagicMock()
        mock_sftp.open.side_effect = IOError("No such file")
        mock_client.open_sftp.return_value = mock_sftp
        MockSSHClient.return_value = mock_client
        source = self._make_source({
            'host': 'h', 'username': 'u', 'password': 'p',
            'remote_path': '/missing.csv',
        })
        imp = self._make_import(source)
        imp.action_fetch()
        self.assertEqual(imp.state, 'error')
        self.assertIn('Cannot read remote file', imp.error_log)

    def test_missing_required_config_field(self):
        source = self._make_source({'host': 'h'})  # no username, no remote_path
        imp = self._make_import(source)
        imp.action_fetch()
        self.assertEqual(imp.state, 'error')
        self.assertIn('username', imp.error_log)

    def test_no_auth_method(self):
        source = self._make_source({
            'host': 'h', 'username': 'u', 'remote_path': '/p',
            # no password, no key_file
        })
        imp = self._make_import(source)
        imp.action_fetch()
        self.assertEqual(imp.state, 'error')
        self.assertIn('password', imp.error_log)

    def test_unknown_host_key_policy(self):
        source = self._make_source({
            'host': 'h', 'username': 'u', 'password': 'p', 'remote_path': '/p',
            'host_key_policy': 'crazy_policy',
        })
        imp = self._make_import(source)
        imp.action_fetch()
        self.assertEqual(imp.state, 'error')
        self.assertIn('host_key_policy', imp.error_log)

    @patch('paramiko.SSHClient')
    def test_full_pipeline_sftp_then_parse(self, MockSSHClient):
        """Fetch JSON через SFTP, потім parse через JSON parser base."""
        payload = b'{"items":[{"code":"A","price":"10"},{"code":"B","price":"20"}]}'
        mock_client, _sftp = self._make_mock_sshclient(payload)
        MockSSHClient.return_value = mock_client
        source = self._make_source({
            'host': 'h', 'username': 'u', 'password': 'p',
            'remote_path': '/prices.json',
        })
        imp = self._make_import(source)
        imp.action_fetch()
        self.assertEqual(imp.state, 'fetched')
        imp.action_parse()
        self.assertEqual(imp.state, 'parsed')
        self.assertEqual(len(imp.line_ids), 2)
