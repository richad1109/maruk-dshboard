from pathlib import Path
import unittest
from unittest.mock import patch
import signal_room
import signal_ui
from tests.test_signal_room import fixture


class ScenarioUI(unittest.TestCase):
    def test_market_switches_render_and_no_private_wallet_calls(self):
        from streamlit.testing.v1 import AppTest
        rows,now=fixture()
        snapshot=dict(reports={c:signal_room.report(c,rows,rows,now) for c in signal_room.COINS},funding={},sentiment=None,errors={},fetched=now)
        signal_ui.room_data.clear()
        with patch('signal_room.fetch',return_value=snapshot),patch('maruk_data.credentials',return_value={}),patch('maruk_data.fetch_portfolio',side_effect=AssertionError('Public scenario page must not read private wallets')):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=25)
            app.query_params['view']='sinyal-auto'
            app.run();self.assertEqual(len(app.exception),0)
            self.assertEqual(app.radio(key='navigation').value,'Sinyal & Skenario')
            for coin in ('SOL','DOGE','BTC'):
                app.selectbox(key='signal_coin').select(coin).run()
                self.assertEqual(len(app.exception),0,coin)
                self.assertEqual(app.query_params['project'],coin.lower())
            self.assertTrue(any('Snapshot funding belum' in x.value for x in app.info))

    def test_missing_market_shows_no_scenario_targets(self):
        from streamlit.testing.v1 import AppTest
        signal_ui.room_data.clear()
        with patch('signal_room.fetch',return_value=dict(reports={},funding={},sentiment=None,errors={},fetched=0)):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=25)
            app.query_params['view']='sinyal-auto';app.run()
            self.assertEqual(len(app.exception),0)
            self.assertFalse(app.dataframe)
            self.assertTrue(any('Analisis BTC belum tersedia' in x.value for x in app.markdown))
