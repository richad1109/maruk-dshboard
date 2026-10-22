import unittest
from btc_research import analyze,HOUR


def fixture():
    start=1700006400
    start=start//(4*HOUR)*(4*HOUR)
    rows=[dict(time=start+i*HOUR,open=100+i,close=100.5+i,high=101+i,low=99+i) for i in range(600)]
    return rows,rows[-1]['time']+HOUR


class TechnicalTests(unittest.TestCase):
    def test_open_candle_cannot_change_analysis(self):
        rows,now=fixture();expected=analyze(rows,now)
        rows.append(dict(time=now,open=10000,high=20000,low=1,close=1))
        actual=analyze(rows,now)
        self.assertEqual(actual,expected)
        self.assertEqual(actual['bias'],'Condong naik')

    def test_gaps_and_stale_data_rejected(self):
        rows,now=fixture()
        with self.assertRaises(ValueError):analyze(rows[:250]+rows[251:],now)
        with self.assertRaises(ValueError):analyze(rows,now+3*HOUR)

    def test_range_excludes_latest_candle(self):
        rows,now=fixture();result=analyze(rows,now)
        self.assertEqual(result['resistance'],rows[-2]['high'])
        self.assertEqual(result['support'],rows[-25]['low'])

    def test_four_hour_boundary_and_bad_prices(self):
        rows,now=fixture()
        self.assertEqual(analyze(rows,now)['four_closed_at']%(4*HOUR),0)
        rows[-1]['close']=float('nan')
        with self.assertRaises(ValueError):analyze(rows,now)
