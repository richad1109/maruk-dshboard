"""Read-only data and Streamlit interaction tests; private APIs are never called."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import os
import unittest

import maruk_data as data


class DataTests(unittest.TestCase):
    def test_eight_wallet_configuration(self):
        self.assertEqual(len(data.ACTIVE),8)
        self.assertNotIn(("akun_3","MEXC"),data.ACTIVE)

    def test_short_in_one_way_bingx(self):
        row=data.normalize_position("BingX",dict(symbol="BTC-USDT",positionAmt="-0.01",positionSide="BOTH",
            avgPrice="100",markPrice="90",initialMargin="1",unrealizedProfit=".1",leverage="25"))
        self.assertEqual(row["side"],"SHORT")
        self.assertEqual(row["symbol"],"BTC/USDT")

    def test_mexc_contract_size_is_not_hardcoded(self):
        raw=dict(symbol="SOL_USDT",holdVol="12",positionType=1,holdAvgPrice="100",im="5")
        row=data.normalize_position("MEXC",raw,{"SOL_USDT":.1})
        self.assertAlmostEqual(row["quantity"],1.2)
        self.assertIsNone(row["mark"])
        self.assertIsNone(row["pnl"])
        self.assertIsNone(data.normalize_position("MEXC",raw,{})["quantity"])

    def test_failed_connection_has_no_fake_online_or_zero_balance(self):
        config={"akun_1":{"BingX":{"apiKey":"test","secret":"test"}}}
        def factory(*_):raise TimeoutError("a signed URL must not be disclosed")
        row=data.query_ledger("akun_1","BingX",config,client_factory=factory)
        self.assertEqual(row["status"],"error")
        self.assertIsNone(row["equity"])
        self.assertEqual(row["error"],"TimeoutError")
        self.assertNotIn("signed",str(row))

    def test_zero_equity_is_valid(self):
        config={"akun_1":{"BingX":{"apiKey":"test","secret":"test"}}}
        client=SimpleNamespace(swapV2PrivateGetUserBalance=lambda:{"code":0,"data":{"balance":{"equity":"0","availableMargin":"0","unrealizedProfit":"0"}}},
            swapV2PrivateGetUserPositions=lambda:{"code":0,"data":[]})
        row=data.query_ledger("akun_1","BingX",config,client_factory=lambda *_:client)
        self.assertEqual(row["status"],"live")
        self.assertEqual(row["equity"],0)

    def test_api_failure_code_cannot_look_successful(self):
        config={"akun_1":{"BingX":{"apiKey":"test","secret":"test"}}}
        client=SimpleNamespace(swapV2PrivateGetUserBalance=lambda:{"code":100001,"data":{}})
        self.assertEqual(data.query_ledger("akun_1","BingX",config,client_factory=lambda *_:client)["status"],"error")

    def test_snapshot_remains_snapshot(self):
        state={"akun_1":{"updated_at":"2024-01-01T00:00:00+00:00","ex_details":{"Bitget":{"total":12,"free":10}},"pos_list":[]}}
        rows=data.snapshot_ledgers(state)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["status"],"snapshot")
        self.assertLess(rows[0]["updated"],1800000000)

    def test_partial_totals_are_explicit_and_missing_pnl_unknown(self):
        one=data.empty_ledger("akun_1","Bitget","live");one.update(equity=10,free=5,floating=1)
        two=data.empty_ledger("akun_1","MEXC","error")
        summary=data.totals({"ledgers":[one,two]})
        self.assertEqual(summary["equity"],10)
        self.assertEqual(summary["live"],1)
        self.assertFalse(summary["complete"])
        self.assertIsNone(summary["floating"])

    def test_empty_portfolio_has_no_fabricated_values(self):
        with patch.object(data,"read_state",return_value={}):snapshot=data.fetch_portfolio({})
        self.assertEqual(len(snapshot["ledgers"]),8)
        self.assertTrue(all(r["status"]=="unconfigured" for r in snapshot["ledgers"]))
        self.assertIsNone(data.totals(snapshot)["equity"])

    def test_state_trade_statistics_are_derived(self):
        result=data.state_metadata({"phase":"growth","wallets":{"akun_1/bitget":{"reserved":12,"trades":[{"net_pnl":-2,"closed":1700000000000},{"net_pnl":5,"closed":1700003600000}]}}})
        self.assertEqual(result["reserved"],12)
        self.assertEqual(sum(r["net_pnl"] for r in result["trades"]),3)
        self.assertEqual(result["trades"][0]["closed"],1700000000)


class AppTests(unittest.TestCase):
    def setUp(self):
        p=patch.object(data,'credentials',return_value={});p.start();self.addCleanup(p.stop)
        p=patch.object(data,'market_data',return_value=dict(tickers=[],candles=[],source='BingX',fetched=None,error=None));p.start();self.addCleanup(p.stop)
    @classmethod
    def setUpClass(cls):
        cls.old=os.environ.get("MARUK_PREVIEW")
        os.environ["MARUK_PREVIEW"]="1"

    @classmethod
    def tearDownClass(cls):
        if cls.old is None:os.environ.pop("MARUK_PREVIEW",None)
        else:os.environ["MARUK_PREVIEW"]=cls.old

    def app(self):
        from streamlit.testing.v1 import AppTest
        with patch.object(data,"credentials",return_value={}),patch.object(data,"market_data",return_value=dict(tickers=[],candles=[],source="BingX",fetched=None,error=None)):
            return AppTest.from_file(str(Path(__file__).resolve().parents[1]/"streamlit_app.py"),default_timeout=20).run()

    def test_all_pages_render_and_are_labelled_preview(self):
        app=self.app()
        self.assertEqual(len(app.exception),0)
        self.assertFalse(any("MODE PRATINJAU" in r.value for r in app.markdown))
        for nav in ["Posisi & Bursa","Bot Sakti","Kantor 3D","Market Intel","Ringkasan"]:
            app.radio(key="navigation").set_value(nav).run()
            self.assertEqual(len(app.exception),0,nav)

    def test_account_market_and_position_filters(self):
        app=self.app()
        app.selectbox(key="account_filter").select("Akun 3").run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.session_state["account"],"akun_3")
        app.selectbox(key="market_filter").select("ETH").run()
        self.assertEqual(len(app.exception),0)
        app.radio(key="navigation").set_value("Posisi & Bursa").run()
        app.selectbox(key="position_direction").select("SHORT").run()
        self.assertEqual(len(app.exception),0)

    def test_no_preview_requests_or_trading_methods(self):
        with patch("requests.get",side_effect=AssertionError("Preview must not request exchange data")),patch("requests.post",side_effect=AssertionError("No AI request without submit")):
            self.assertEqual(len(self.app().exception),0)
        source=(Path(__file__).resolve().parents[1]/"maruk_data.py").read_text()
        for method in ["create_order(","cancel_order(","set_leverage(","transfer(","withdraw("]:
            self.assertNotIn(method,source)


if __name__=="__main__":unittest.main()
