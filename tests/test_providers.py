import hashlib
import hmac
import json
import os
import sqlite3
import unittest
from unittest.mock import patch
from app.core import Problem
from app.providers import ingest_event,provider_status,prepare_trulioo_business,execute_trulioo_business,TRULIOO_ENDPOINT,NoRedirect
import urllib.error

class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.executescript('''
          CREATE TABLE provider_events(id TEXT PRIMARY KEY,provider TEXT NOT NULL,event_id TEXT NOT NULL,subject_reference TEXT NOT NULL,event_type TEXT NOT NULL,provider_status TEXT NOT NULL,normalized_status TEXT NOT NULL,occurred_at TEXT NOT NULL,received_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL,provider_timestamp INTEGER NOT NULL,normalized_json TEXT NOT NULL,UNIQUE(provider,event_id));
          CREATE TABLE eligibility(user_id TEXT,state TEXT);
          INSERT INTO eligibility VALUES('synthetic-subject','PENDING_REVIEW');
          CREATE TABLE holdings(id TEXT);
          CREATE TABLE transactions(id TEXT);
        ''')
        self.epoch=1790000000
        self.secret='synthetic-test-signing-secret-not-for-deployment'
        self.env=patch.dict(os.environ,{'RAN_REVIEW_BRIDGE_WEBHOOK_SECRET':self.secret},clear=True);self.env.start()
        self.config={'enabled':True}
        self.event={'event_id':'synthetic-event-1','subject_reference':'synthetic-subject','event_type':'BUSINESS_VERIFICATION_RESULT','occurred_at':'2026-01-01T00:00:00Z','result':{'status':'match','reference':'synthetic-source-1'}}
        self.business={'business_name':'SYNTHETIC DEMO BUSINESS','business_registration_number':'DEMO123','jurisdiction_of_incorporation':'ON','customer_reference':'synthetic-request-1','synthetic':True}

    def tearDown(self):self.env.stop();self.c.close()
    def raw(self):return json.dumps(self.event,separators=(',',':')).encode()
    def headers(self,body,timestamp=None):
        timestamp=str(self.epoch if timestamp is None else timestamp)
        return {'X-RAN-Event-Timestamp':timestamp,'X-RAN-Event-Signature':'sha256='+hmac.new(self.secret.encode(),timestamp.encode()+b'.'+body,hashlib.sha256).hexdigest()}
    def ingest(self,body=None,headers=None,**kwargs):
        body=self.raw() if body is None else body
        return ingest_event(self.c,'signed_review_bridge',body,self.headers(body) if headers is None else headers,kwargs.get('config',self.config),now_epoch=self.epoch)

    def test_signature_raw_bytes_and_timestamp_are_required(self):
        body=self.raw()
        for headers in [{},self.headers(body+b' '),self.headers(body,self.epoch-301),self.headers(body,self.epoch+301)]:
            with self.subTest(headers=headers),self.assertRaises(Problem) as error:self.ingest(body,headers)
            self.assertEqual(error.exception.status,401)
        self.assertEqual(self.c.execute('SELECT count(*) FROM provider_events').fetchone()[0],0)

    def test_replay_is_idempotent_but_changed_payload_conflicts(self):
        first=self.ingest();second=self.ingest()
        self.assertEqual(first['receipt_id'],second['receipt_id']);self.assertTrue(second['replayed'])
        self.event['result']['status']='nomatch'
        with self.assertRaises(Problem) as error:self.ingest()
        self.assertEqual(error.exception.status,409);self.assertEqual(self.c.execute('SELECT count(*) FROM provider_events').fetchone()[0],1)

    def test_receipt_never_changes_eligibility_or_financial_state(self):
        result=self.ingest();self.assertEqual(result['event']['normalized_status'],'MATCH')
        self.assertEqual(self.c.execute('SELECT state FROM eligibility').fetchone()[0],'PENDING_REVIEW')
        self.assertEqual(self.c.execute('SELECT count(*) FROM holdings').fetchone()[0],0)
        self.assertEqual(self.c.execute('SELECT count(*) FROM transactions').fetchone()[0],0)
        self.assertTrue(result['event']['human_review_required']);self.assertFalse(result['eligibility_changed'])

    def test_unknown_vendor_status_remains_unknown(self):
        self.event['result']['status']='APPROVED'
        result=self.ingest();self.assertEqual(result['event']['normalized_status'],'UNKNOWN')
        self.assertEqual(result['event']['provider_status'],'APPROVED')

    def test_disabled_missing_key_and_native_webhook_fail_closed(self):
        with self.assertRaises(Problem) as error:self.ingest(config={})
        self.assertEqual(error.exception.status,503)
        with patch.dict(os.environ,{},clear=True),self.assertRaises(Problem):self.ingest()
        with self.assertRaises(Problem):ingest_event(self.c,'trulioo_business',self.raw(),self.headers(self.raw()),self.config,now_epoch=self.epoch)

    def test_payload_schema_and_duplicate_keys_are_rejected(self):
        self.event['grant_eligibility']=True
        with self.assertRaises(Problem):self.ingest()
        del self.event['grant_eligibility']
        self.event['event_type']=[]
        with self.assertRaises(Problem):self.ingest()
        body=b'{"event_id":"one","event_id":"two"}'
        with self.assertRaises(Problem):self.ingest(body)
        self.assertEqual(self.c.execute('SELECT count(*) FROM provider_events').fetchone()[0],0)

    def test_provider_status_never_discloses_credentials_or_claims_connection(self):
        result=provider_status({'signed_review_bridge':{'enabled':True}})
        self.assertNotIn(self.secret,json.dumps(result));self.assertFalse(result['external_accounts_verified'])
        self.assertEqual(result['providers'][0]['state'],'CONFIGURED_NOT_VALIDATED')
        trulioo=next(item for item in result['providers'] if item['id']=='trulioo_business')
        self.assertEqual(trulioo['state'],'DISABLED');self.assertFalse(trulioo['outbound_enabled'])

    def test_trulioo_demo_request_is_fixed_and_never_infers_consent(self):
        with patch.dict(os.environ,{'RAN_TRULIOO_PACKAGE_ID':'synthetic-package'}):
            prepared=prepare_trulioo_business(self.business,{})
            self.assertEqual(prepared['url'],TRULIOO_ENDPOINT);self.assertEqual(prepared['body']['VerificationType'],'Demo')
            self.assertEqual(prepared['body']['CountryCode'],'CA');self.assertEqual(prepared['body']['ConsentForDataSources'],[])
            self.assertFalse(prepared['transmitted']);self.assertNotIn('Authorization',prepared)
            with self.assertRaises(Problem):prepare_trulioo_business(self.business|{'url':'https://demo.invalid'},{})
            with self.assertRaises(Problem):prepare_trulioo_business(self.business|{'synthetic':False},{})

    def test_outbound_requires_configuration_and_exact_authorized_digest(self):
        with patch('app.providers.urllib.request.build_opener') as opener:
            with self.assertRaises(Problem):execute_trulioo_business(self.business,'approved-action','wrong',{})
            with patch.dict(os.environ,{'RAN_TRULIOO_PACKAGE_ID':'synthetic-package'}):
                with self.assertRaises(Problem):execute_trulioo_business(self.business,'approved-action','wrong',{'enabled':True,'outbound_enabled':True})
            opener.assert_not_called()

    def test_authenticated_transport_is_demo_only_and_does_not_return_raw_pii(self):
        config={'enabled':True,'outbound_enabled':True}
        with patch.dict(os.environ,{'RAN_TRULIOO_PACKAGE_ID':'synthetic-package','RAN_TRULIOO_BEARER_TOKEN':'synthetic-bearer-token'}):
            prepared=prepare_trulioo_business(self.business,config)
            with patch('app.providers.urllib.request.build_opener') as builder:
                response=builder.return_value.open.return_value.__enter__.return_value
                response.status=200;response.read.return_value=b'{"Record":{"RecordStatus":"match","TransactionRecordID":"synthetic-record"},"private_data":"SYNTHETIC OMITTED FIELD"}'
                result=execute_trulioo_business(self.business,'approved-action',prepared['request_sha256'],config)
                request=builder.return_value.open.call_args.args[0]
                self.assertEqual(request.full_url,TRULIOO_ENDPOINT);self.assertEqual(request.get_header('Authorization'),'Bearer synthetic-bearer-token')
                self.assertEqual(result['normalized_status'],'MATCH');self.assertNotIn('private_data',json.dumps(result));self.assertFalse(result['eligibility_changed'])

    def test_redirects_are_never_followed(self):
        import urllib.request
        with self.assertRaises(urllib.error.HTTPError):NoRedirect().redirect_request(urllib.request.Request(TRULIOO_ENDPOINT),None,302,'redirect',{},'https://demo.invalid')

if __name__=='__main__':unittest.main()
