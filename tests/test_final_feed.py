import base64
import hashlib
import json
import time
import unittest
from cryptography.fernet import Fernet,InvalidToken
import final_feed

class FinalFeedTests(unittest.TestCase):
    def setUp(self):
        self.accounts={'akun_1':{'Bitget':{'apiKey':'test-api','secret':'test-secret'}}}
        self.key=base64.urlsafe_b64encode(hashlib.sha256(b'bot-final-monitor-v1|test-api|test-secret').digest())
        self.state={'schema':'sakti-monitor-v1','version':'bot-final-btc-h96-t3-r1','wallets':{},'updated_at':time.time()*1000}
    def test_encrypted_roundtrip(self):
        data=Fernet(self.key).encrypt(json.dumps(self.state).encode())
        self.assertEqual(final_feed.decrypt(data,self.accounts),self.state)
        self.assertNotIn(b'test-secret',data)
    def test_tampering_rejected(self):
        data=Fernet(self.key).encrypt(json.dumps(self.state).encode())
        with self.assertRaises(InvalidToken):final_feed.decrypt(data[:-5]+b'abcde',self.accounts)
    def test_future_heartbeat_rejected(self):
        self.state['updated_at']+=3600000
        data=Fernet(self.key).encrypt(json.dumps(self.state).encode())
        with self.assertRaises(ValueError):final_feed.decrypt(data,self.accounts)
