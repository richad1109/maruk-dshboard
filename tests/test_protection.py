import unittest
from unittest.mock import Mock
from maruk_data import check_protection


class ProtectionTests(unittest.TestCase):
    def test_missing_take_is_unverified(self):
        client=Mock()
        client.fetch_open_orders.return_value=[{'type':'STOP_MARKET','stopPrice':90}]
        result=check_protection(client,'BingX',{'symbol':'SOL/USDT','side':'LONG'})
        self.assertEqual(result['status'],'unverified')

    def test_opposite_side_and_cancelled_orders_not_counted(self):
        client=Mock()
        client.fetch_open_orders.return_value=[
            {'stopLossPrice':90,'takeProfitPrice':130,'info':{'positionSide':'SHORT'}},
            {'stopLossPrice':90,'takeProfitPrice':130,'status':'canceled'}]
        self.assertEqual(check_protection(client,'BingX',{'symbol':'SOL/USDT','side':'LONG'})['status'],'unverified')

    def test_bitget_trigger_read(self):
        client=Mock()
        client.fetch_open_orders.side_effect=[[],[
            {'info':{'planType':'pos_loss','triggerPrice':'90'}},
            {'info':{'planType':'pos_profit','triggerPrice':'130'}}]]
        self.assertEqual(check_protection(client,'Bitget',{'symbol':'SOL/USDT','side':'LONG'})['status'],'detected')
