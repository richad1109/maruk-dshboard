import math
import unittest
from unittest.mock import Mock,patch
import signal_room as room


def fixture(scale=1):
    start=1700006400//(4*room.HOUR)*(4*room.HOUR)
    rows=[]
    for i in range(1000):
        close=100*math.exp(i*.0025)*scale;op=close/math.exp(.0025)
        rows.append(dict(time=start+i*room.HOUR,open=op,close=close,high=close*1.0001,low=op*.9999,volume=100))
    return rows,rows[-1]['time']+room.HOUR


class ScenarioTests(unittest.TestCase):
    def test_alt_confirmation_and_plan_arithmetic(self):
        btc,now=fixture();alt,_=fixture(2)
        r=room.report('SOL',alt,btc,now)
        self.assertTrue(r['eligible']);self.assertEqual(r['side'],1)
        self.assertAlmostEqual(r['correlation'],1)
        for p in r['plans']:
            self.assertAlmostEqual(abs(p['tp']-p['entry'])/abs(p['entry']-p['sl']),10)
        self.assertEqual(r['volume_ratio'],1)

    def test_open_candle_cannot_change_report(self):
        rows,now=fixture();before=room.report('BTC',rows,now=now)
        rows.append(dict(time=now,open=1,high=1e8,low=.01,close=1,volume=1e9))
        self.assertEqual(before,room.report('BTC',rows,now=now))

    def test_missing_or_stale_btc_never_confirms_alt(self):
        rows,now=fixture()
        for btc in (None,rows[:-10]):
            r=room.report('SOL',rows,btc,now)
            self.assertFalse(r['eligible']);self.assertIsNone(r['correlation'])
            self.assertEqual(r['state'],'Tunggu konfirmasi')

    def test_gap_and_invalid_price_rejected(self):
        rows,now=fixture()
        with self.assertRaises(ValueError):room.report('BTC',rows[:300]+rows[301:],now=now)
        rows[-1]['close']=float('nan')
        with self.assertRaises(ValueError):room.report('BTC',rows,now=now)

    def test_prior_range_and_projection_not_future_price(self):
        rows,now=fixture();r=room.report('BTC',rows,now=now)
        self.assertEqual(r['scenarios'][0]['trigger'],max(x['high'] for x in rows[-25:-1]))
        self.assertAlmostEqual(r['scenarios'][0]['target1']-r['scenarios'][0]['trigger'],r['technical']['atr'])

    def premium(self,now,age=3600,symbol='BTC-USDT'):
        return dict(code=0,data=dict(symbol=symbol,markPrice='100',indexPrice='99',lastFundingRate='0.0001',
            nextFundingTime=int((now+3600)*1000),updateTime=int((now-age)*1000),fundingIntervalHours=8))

    def test_rate_timestamp_is_not_mislabelled_as_tick_timestamp(self):
        now=1700000000;r=Mock();r.json.return_value=self.premium(now,age=7200)
        with patch('signal_room.requests.get',return_value=r):out=room.get_funding('BTC',now)
        self.assertEqual(out['updated_at'],now-7200);self.assertEqual(out['observed_at'],now)
        self.assertEqual(out['rate_pct'],.01)

    def test_stale_and_wrong_market_funding_rejected(self):
        now=1700000000;r=Mock()
        for payload in (self.premium(now,age=10*3600),self.premium(now,symbol='SOL-USDT')):
            r.json.return_value=payload
            with patch('signal_room.requests.get',return_value=r):
                with self.assertRaises(ValueError):room.get_funding('BTC',now)

    def test_partial_fetch_does_not_fabricate_missing_data(self):
        rows,now=fixture()
        with patch('signal_room.get_candles',return_value=rows),patch('signal_room.get_funding',side_effect=TimeoutError),patch('signal_room.btc_research.fetch_sentiment',side_effect=TimeoutError),patch('signal_room.time.time',return_value=now):
            result=room.fetch()
        self.assertEqual(len(result['reports']),3)
        self.assertEqual(result['funding'],{});self.assertIsNone(result['sentiment'])
        self.assertEqual(len(result['errors']),4)
