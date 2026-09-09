import base64, hashlib
import test_kernel as fixtures
from app.core import *

class PrivateIntakeTests(fixtures.KernelTests):
    # Reuse isolated fixture setup without inheriting the kernel test methods below.
    def test_real_intake_stays_private(self):
        p=create_property(self.c,self.b,{'address':'Synthetic test of private intake','city':'Toronto','property_type':'OFFICE','units':1,'asking_price':1000000,'data_classification':'REAL_PRIVATE','rights_attested':True,'source_reference':'Synthetic private MLS fixture'})['property']
        self.assertEqual(p['synthetic'],0)
        self.ready(p['id'])
        with self.assertRaises(Problem):self.action(self.a,'PUBLISH_PROPERTY',p['id'])
        with self.assertRaises(Problem):self.action(self.a,'CREATE_OFFERING',p['id'])
        public=__import__('app.service',fromlist=['dispatch']).dispatch(self.c,None,'GET','/api/properties')['properties']
        self.assertNotIn(p['id'],[v['id'] for v in public])
    def test_real_intake_requires_authority_statement(self):
        with self.assertRaises(Problem):create_property(self.c,self.b,{'address':'Synthetic','city':'Toronto','units':1,'asking_price':1000000,'data_classification':'REAL_PRIVATE','source_reference':'Fixture'})
    def test_binary_original_quarantine_no_extraction(self):
        pid=self.draft();raw=b'%PDF-1.7\nSynthetic inert fixture\n%%EOF'
        result=upload_binary(self.c,self.b,pid,{'filename':'sample.pdf','content_base64':base64.b64encode(raw).decode()})
        self.assertEqual(result['artifact']['state'],'QUARANTINED');self.assertEqual(result['claims'],[])
        saved=one(self.c,'SELECT * FROM artifact_blobs WHERE artifact_id=?',(result['artifact']['id'],))
        self.assertEqual(saved['raw_bytes'],raw);self.assertEqual(result['artifact']['sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(risk_state(self.c,pid)['quarantined_artifacts'],1)
    def test_binary_signature_and_path_and_tenant_checks(self):
        pid=self.draft()
        for name,raw in [('../bad.pdf',b'%PDF-'),('spoof.pdf',b'MZnotpdf'),('macro.docm',b'PK')]:
            with self.assertRaises(Problem):upload_binary(self.c,self.b,pid,{'filename':name,'content_base64':base64.b64encode(raw).decode()})
        with self.assertRaises(Problem):upload_binary(self.c,self.i,pid,{'filename':'sample.pdf','content_base64':base64.b64encode(b'%PDF-').decode()})
    def test_development_not_forced_into_income_model(self):
        p=create_property(self.c,self.b,{'address':'Synthetic development','city':'Toronto','property_type':'DEVELOPMENT','units':1,'asking_price':1000000})['property']
        with self.assertRaises(Problem):underwrite(self.c,self.b,p['id'],{})

# Avoid rerunning inherited tests; retain only fixture/helper methods.
for _name in dir(fixtures.KernelTests):
    if _name.startswith('test_'):setattr(PrivateIntakeTests,_name,None)
