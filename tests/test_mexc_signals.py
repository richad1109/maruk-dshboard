import unittest
from unittest.mock import patch
import mexc_signals as m

def rows(n=700):
    return [dict(time=1700002800+i*3600,open=100+i*.03,high=101+i*.03,low=99+i*.03,close=100.4+i*.03,vol=100) for i in range(n)]

class ScannerTests(unittest.TestCase):
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
            a=AppTest.from_file(str(__import__('pathlib').Path(__file__).resolve().parents[1]/'streamlit_app.py'));a.query_params['view']='sinyal-kripto';a.run()
            self.assertFalse(a.exception)
            self.assertNotIn('Kantor 3D',a.radio[0].options)
if __name__=='__main__':unittest.main()
