import unittest
import sakti_monitor as monitor


class SaktiTelemetryTests(unittest.TestCase):
    def test_allowlist_removes_keys_and_api_identity(self):
        raw=dict(apiKey='must-not-escape',wallets={'akun_1/bingx':dict(identity='must-not-escape',secret='must-not-escape',positions={},trades=[])})
        cleaned=monitor.sanitize(raw)
        self.assertNotIn('must-not-escape',str(cleaned))
        self.assertEqual(list(cleaned['wallets']),['akun_1/bingx'])

    def test_alerts_survive_export_and_upload(self):
        raw=dict(wallets={'akun_1/bingx':dict(trades=[],positions={'SOL/USDT:USDT':dict(protection_warning='missing_server_sl',stop=100,take=120)})})
        once=monitor.sanitize(raw);twice=monitor.sanitize(once)
        self.assertEqual(twice['alerts'],once['alerts'])
        self.assertEqual(twice['alerts'][0]['sl'],100)

    def test_sizing_health_ignores_unmatured_future_outcome(self):
        state=dict(wallets={'akun_1/bitget':dict(positions={},trades=[dict(closed=n*3600000,net_pnl=1,net_R=1) for n in range(4)])})
        self.assertEqual(monitor.metrics(state,now=3*3600)['wallets'][0]['scale'],.25)
        self.assertEqual(monitor.metrics(state,now=4*3600)['wallets'][0]['scale'],1)

    def test_missing_journal_does_not_fabricate_profit(self):
        self.assertIsNone(monitor.metrics({})['realized'])
        with self.assertRaises(ValueError):monitor.sanitize({'apiKey':'bad-upload'})
