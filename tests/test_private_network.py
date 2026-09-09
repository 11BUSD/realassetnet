import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import Problem
from app.private_network import ORG_FIELDS, external_database, handle, read_connection
from scripts.configure_private_network import configure

class PrivateNetworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.public=self.root/'public';self.public.mkdir()
        self.db=self.root/'synthetic-research.sqlite';self.config=self.public/'runtime'/'private-network.json';self.key_path=self.public/'runtime'/'operator.key'
        self.today=datetime.now(timezone.utc).date().isoformat();c=sqlite3.connect(self.db)
        c.execute('CREATE TABLE organizations('+','.join(name+' TEXT' for name in ORG_FIELDS)+')')
        c.executescript('''
          CREATE TABLE sources(source_id TEXT,url TEXT);
          CREATE TABLE people(person_id TEXT,organization_id TEXT,full_name TEXT,title TEXT,role_category TEXT,location TEXT,verification_state TEXT,last_verified TEXT);
          CREATE TABLE mandates(mandate_id TEXT);
          CREATE TABLE organization_roles(organization_id TEXT,role TEXT);
          CREATE TABLE scores(organization_id TEXT,factor TEXT,raw_score REAL,max_raw REAL,weight REAL,weighted_points REAL,rationale TEXT,source_id TEXT);
          CREATE TABLE network_factors(organization_id TEXT,factor TEXT,score REAL,max_score REAL,rationale TEXT,source_id TEXT);
          CREATE TABLE contacts(contact_id TEXT,organization_id TEXT,person_id TEXT,value TEXT,channel TEXT,verification_state TEXT,last_verified TEXT,consent_status TEXT,deliverability_status TEXT,source_id TEXT);
          CREATE TABLE trigger_events(trigger_id TEXT,trigger TEXT,event_date TEXT,verification_state TEXT,source_id TEXT);
          CREATE TABLE outreach_queue(queue_id TEXT,organization_id TEXT,person_id TEXT,priority INTEGER,angle TEXT,reason TEXT,value_proposition TEXT,recommended_ask TEXT,contact_channel TEXT,status TEXT,prepared_at TEXT,not_before TEXT,next_action TEXT,contact_id TEXT,source_id TEXT,trigger_id TEXT);
          CREATE TABLE relationships(relationship_id INTEGER,from_organization_id TEXT,to_organization_id TEXT,relationship_type TEXT,description TEXT,source_id TEXT,last_verified TEXT,verification_state TEXT,relationship_scope TEXT,permission_to_introduce TEXT);
          CREATE TABLE interaction_history(interaction_id INTEGER,organization_id TEXT,person_id TEXT,status_after TEXT,occurred_at TEXT);
        ''')
        org={name:None for name in ORG_FIELDS};org.update(organization_id='demo-org',brand_name='DEMO Research Institution',fit_score=88,network_group_id='demo-group',relationship_status='RESEARCH',verification_state='VERIFIED',last_verified=self.today,source_urls='["https://demo.invalid/source"]',asset_classes='["MULTIFAMILY"]',why_this_counterparty='Synthetic finance research example')
        c.execute('INSERT INTO organizations VALUES('+','.join('?' for _ in ORG_FIELDS)+')',[org[name] for name in ORG_FIELDS])
        c.execute('INSERT INTO sources VALUES(?,?)',('source-1','https://demo.invalid/source'))
        c.execute('INSERT INTO people VALUES(?,?,?,?,?,?,?,?)',('person-1','demo-org','Demo Professional','Head of Finance','LENDER','Toronto','VERIFIED',self.today))
        c.execute('INSERT INTO organization_roles VALUES(?,?)',('demo-org','LENDER'))
        c.execute('INSERT INTO scores VALUES(?,?,?,?,?,?,?,?)',('demo-org','EVIDENCE_CONFIDENCE',4,5,10,8,'Official synthetic evidence','source-1'))
        c.execute('INSERT INTO network_factors VALUES(?,?,?,?,?,?)',('demo-org','REACH',15,25,'Synthetic estimate','source-1'))
        c.execute('INSERT INTO contacts VALUES(?,?,?,?,?,?,?,?,?,?)',('contact-1','demo-org','person-1','professional@demo.invalid','EMAIL','VERIFIED',self.today,'UNKNOWN','NOT_TESTED','source-1'))
        c.execute('INSERT INTO trigger_events VALUES(?,?,?,?,?)',('trigger-1','Synthetic financing expansion',self.today,'VERIFIED','source-1'))
        c.execute('INSERT INTO outreach_queue VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('queue-1','demo-org','person-1',1,'Synthetic angle','Synthetic reason','Review a demo workflow','Ask for mandate confirmation','EMAIL','READY',self.today,None,'Prepare a reviewed draft','contact-1','source-1','trigger-1'))
        c.execute('INSERT INTO relationships VALUES(?,?,?,?,?,?,?,?,?,?)',(1,'demo-org','demo-org','SYNTHETIC_TEST_EDGE','Synthetic documented edge','source-1',self.today,'VERIFIED','EXTERNAL_DOCUMENTED','UNKNOWN'))
        c.commit();c.close()
        configure(self.db,self.config,self.key_path,self.public);self.key=self.key_path.read_text().strip();self.admin={'id':'synthetic-admin','organization_id':'synthetic-operator','role':'admin'}

    def tearDown(self): self.tmp.cleanup()
    def request(self,**kwargs):
        args={'c':None,'u':self.admin,'method':'GET','path':'/api/network','d':{},'key':self.key,'config_path':self.config};args.update(kwargs);return handle(**args)
    def change(self,sql,args=()):
        c=sqlite3.connect(self.db);c.execute(sql,args);c.commit();c.close()

    def test_admin_and_operator_key_are_both_required(self):
        for changes in [{'u':None},{'u':{'role':'broker'}},{'key':'wrong'},{'key':None}]:
            with self.subTest(changes=changes),self.assertRaises(Problem) as error: self.request(**changes)
            self.assertEqual(error.exception.status,403)

    def test_unconfigured_is_closed_status_has_no_path_or_key(self):
        status=self.request(path='/api/network/status',key=None)
        self.assertTrue(status['configured']);self.assertNotIn('database',status);self.assertNotIn('operator_key_sha256',status)
        missing=self.public/'runtime'/'missing.json'
        self.assertFalse(self.request(path='/api/network/status',config_path=missing,key=None)['configured'])
        with self.assertRaises(Problem) as error:self.request(config_path=missing)
        self.assertEqual(error.exception.status,503)

    def test_private_snapshot_is_read_only_and_retains_sources(self):
        before=hashlib.sha256(self.db.read_bytes()).hexdigest();result=self.request()
        self.assertEqual(result['mode'],'PRIVATE_READ_ONLY');self.assertEqual(result['summary']['sources'],1)
        self.assertEqual(result['organizations'][0]['roles'],['LENDER']);self.assertTrue(result['organizations'][0]['score_breakdown'][0]['source_url'])
        self.assertEqual(result['queue'][0]['verified_contact'],'professional@demo.invalid');self.assertFalse(result['queue'][0]['outreach_enabled'])
        self.assertEqual(result['relationships'][0]['permission_to_introduce'],'UNKNOWN')
        c=read_connection(self.db)
        try:
            with self.assertRaises(sqlite3.DatabaseError):c.execute("UPDATE organizations SET brand_name='changed'")
            with self.assertRaises(sqlite3.DatabaseError):c.execute("ATTACH DATABASE ':memory:' AS other")
        finally:c.close()
        self.assertEqual(before,hashlib.sha256(self.db.read_bytes()).hexdigest())

    def test_stale_future_and_unverified_contact_values_are_withheld(self):
        old=(datetime.now(timezone.utc).date()-timedelta(days=31)).isoformat()
        future=(datetime.now(timezone.utc).date()+timedelta(days=1)).isoformat()
        for value in (old,future,'not-a-date'):
            self.change('UPDATE contacts SET last_verified=?',(value,));row=self.request()['queue'][0]
            self.assertEqual(row['status'],'RESEARCH');self.assertIsNone(row['verified_contact'])
        self.change("UPDATE contacts SET last_verified=?,verification_state='UNVERIFIED'",(self.today,))
        self.assertIsNone(self.request()['queue'][0]['verified_contact'])

    def test_contacted_suppression_history_and_not_before(self):
        for status in ['CONTACTED','DO_NOT_CONTACT','NOT_NOW','PARTNER']:
            self.change('UPDATE organizations SET relationship_status=?',(status,));self.assertEqual(self.request()['queue'],[])
        self.change("UPDATE organizations SET relationship_status='RESEARCH'")
        self.change("INSERT INTO interaction_history VALUES(1,'demo-org','person-1','DO_NOT_CONTACT',?)",(self.today,));self.assertEqual(self.request()['queue'],[])
        self.change('DELETE FROM interaction_history');self.change('UPDATE outreach_queue SET not_before=?',((datetime.now(timezone.utc).date()+timedelta(days=1)).isoformat(),));self.assertEqual(self.request()['queue'],[])
        self.change("UPDATE outreach_queue SET not_before=NULL,status='CONTACTED'");self.assertEqual(self.request()['queue'],[])

    def test_public_source_and_mutation_routes_are_refused(self):
        inside=self.public/'runtime'/'synthetic.sqlite';inside.write_bytes(self.db.read_bytes())
        with self.assertRaises(Problem):external_database(inside,self.public)
        with self.assertRaises(Problem):configure(inside,self.config,self.key_path,self.public)
        with self.assertRaises(Problem) as error:self.request(method='POST')
        self.assertEqual(error.exception.status,405)

    def test_configuration_is_exclusive_and_never_returns_key(self):
        config=json.loads(self.config.read_text());self.assertEqual(config['operator_key_sha256'],hashlib.sha256(self.key.encode()).hexdigest())
        self.assertNotIn(self.key,self.config.read_text())
        with self.assertRaises(Problem):configure(self.db,self.config,self.key_path,self.public)
        self.assertEqual(self.key,self.key_path.read_text().strip())

if __name__=='__main__':unittest.main()
