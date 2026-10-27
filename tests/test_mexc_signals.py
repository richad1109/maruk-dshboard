import unittest
from unittest.mock import patch
import mexc_signals as m

def rows(n=700):
    return [dict(time=1700002800+i*3600,open=100+i*.03,high=101+i*.03,low=99+i*.03,close=100.4+i*.03,vol=100) for i in range(n)]

class ScannerTests(unittest.TestCase):
    def setUp(self):
        p=patch('mexc_signal_ui.bias_data',return_value=[]);p.start();self.addCleanup(p.stop)

    def test_closed_and_gaps(self):
        r=rows();now=r[-1]['time']+3600
        self.assertEqual(len(m.clean(r+[dict(r[-1],time=now)],now)),700)
        with self.assertRaises(ValueError):m.clean(r[:300]+r[301:],now)
    def test_causal_features(self):
        r=rows();self.assertEqual(m.features(r)[:400],m.features(r[:400]))
    def test_same_bar_stop_first_and_fees(self):
        r=rows(110);r[102].update(high=120,low=80)
        f=m.features(r)
        with patch.object(m,'side_at',side_effect=lambda rows,f,i,rule:1 if i==101 else 0):
            t=m.replay(r,f,'test',100,110,.001,.0005,.0001)['trades'][0]
        self.assertEqual(t['reason'],'SL');self.assertLess(t['net_pct'],0)
    def test_no_90_label_without_evidence(self):
        r=rows();out=m.evaluate(r,dict(symbol='X_USDT',fee=.0001,volume=10000000,spread=.01),now=r[-1]['time']+3600)
        self.assertFalse(out['target90']);self.assertFalse(out['qualified'])
    def test_catalog_filters_and_missing_spread(self):
        with patch.object(m,'get',side_effect=[[dict(symbol='X_USDT',quoteCoin='USDT',state=0),dict(symbol='OLD_USDT',quoteCoin='USDT',state=1)],[dict(symbol='X_USDT')]]):c=m.catalog()
        self.assertEqual(len(c),1);self.assertIsNone(c[0]['spread'])
    def test_no_private_calls_ui(self):
        from streamlit.testing.v1 import AppTest
        with patch('mexc_signal_ui.universe',return_value=[dict(symbol='BTC_USDT')]),patch('mexc_signal_ui.batch',return_value=[dict(symbol='BTC_USDT',error='test',message='test')]),patch('maruk_ui.portfolio',side_effect=AssertionError('private read')):
            a=AppTest.from_file(str(__import__('pathlib').Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=20);a.query_params['view']='sinyal-kripto';a.run()
            self.assertFalse(a.exception)
            self.assertNotIn('Kantor 3D',a.radio[0].options)
class CompactBoardTests(unittest.TestCase):
    def setUp(self):
        p=patch('mexc_signal_ui.bias_data',return_value=[]);p.start();self.addCleanup(p.stop)
    def test_bias_is_causal_and_stale_rejected(self):
        r=rows();now=r[-1]['time']+3600
        a=m.market_bias(r,now);self.assertEqual(a['side'],1)
        self.assertEqual(a,m.market_bias(r+[dict(r[-1],time=now,close=99999,high=99999)],now))
        with self.assertRaises(ValueError):m.market_bias(r,now+10800)

    def signal(self):
        return dict(symbol='BTC_USDT',rule='Donchian breakout',side=1,entry=100,tp=104,sl=98,
            published=120,closed=100,expires=400,qualified=True,liquid=True,target90=True,
            test=dict(n=110,wr=92,lower=85,pf=2,mean_r=.3))
    def test_conditional_plans_are_directional_not_accuracy_claims(self):
        obs=dict(atr=2,support=90,resistance=110,closed=100)
        long=m.bias_plan(obs,1);short=m.bias_plan(obs,-1)
        self.assertLess(long['sl'],long['entry']);self.assertLess(long['entry'],long['tp'])
        self.assertGreater(short['sl'],short['entry']);self.assertGreater(short['entry'],short['tp'])
        self.assertAlmostEqual((long['tp']-long['entry'])/(long['entry']-long['sl']),2)
        self.assertNotIn('wr',long)
    def test_strict_gate_and_conflict(self):
        from mexc_signal_ui import visible_signals
        r=self.signal();self.assertEqual(len(visible_signals([r],now=200)),1)
        self.assertFalse(visible_signals([{**r,'test':{**r['test'],'n':10}}],now=200))
        self.assertFalse(visible_signals([r],now=500))
        self.assertFalse(visible_signals([r,{**r,'side':-1}],now=200))
    def test_level_touch_ambiguous_short_and_expiry(self):
        r=self.signal()
        self.assertEqual(m.touch_status(r,[dict(time=180,high=105,low=97)])['status'],'AMBIGU')
        self.assertEqual(m.touch_status({**r,'side':-1,'tp':96,'sl':102},[dict(time=180,high=101,low=95)])['status'],'TP')
        self.assertEqual(m.touch_status(r,[dict(time=480,high=105,low=99)])['status'],'KEDALUWARSA')
        self.assertNotEqual(m.touch_status({**r,'published':125},[dict(time=120,high=105,low=97)])['status'],'AMBIGU')
    def test_cards_without_tables_or_method_controls(self):
        from streamlit.testing.v1 import AppTest
        r=self.signal();r.update(closed=__import__('time').time()-60,expires=__import__('time').time()+300)
        with patch('mexc_signal_ui.universe',return_value=[dict(symbol='BTC_USDT')]),patch('mexc_signal_ui.batch',return_value=[dict(symbol='BTC_USDT',candidates=[r])]),patch('mexc_signal_ui.touch',return_value=dict(status='TP',at=180)):
            a=AppTest.from_file(str(__import__('pathlib').Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=20);a.query_params['view']='sinyal-kripto';a.run()
            self.assertFalse(a.exception);self.assertEqual(len(a.dataframe),0);self.assertEqual(len(a.selectbox),0)
            self.assertTrue(any('TP TERSENTUH' in x.value for x in a.markdown))

if __name__=='__main__':unittest.main()
