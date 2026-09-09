import sqlite3, unittest, importlib.util
from types import SimpleNamespace
from unittest.mock import patch
from app.identity import authenticate,resolve_user,validate_config,public_config
from app.core import Problem

CONFIG={'mode':'clerk','issuer':'https://identity.example.test','authorized_parties':['http://localhost:8080'],'publishable_key':'pk_test_fixture','secret_key':'sk_test_fixture'}
CLAIMS={'iss':CONFIG['issuer'],'azp':'http://localhost:8080','sub':'user_fixture','sid':'sess_fixture','org_id':'org_fixture','role':'admin','email':'reviewer@demo.invalid'}
class IdentityTests(unittest.TestCase):
    def auth(self,payload=None,signed=True):
        with patch('app.identity._sdk_authenticate',return_value=SimpleNamespace(is_signed_in=signed,payload=payload or CLAIMS)) as call:
            result=authenticate({'Authorization':'Bearer unsigned-test-boundary-placeholder'},'http://localhost:8080/api/session',CONFIG)
            self.assertEqual(call.call_args.args[0].headers.keys(),{'Authorization'})
            return result
    def test_sdk_result_allowlist_removes_role_email(self):
        result=self.auth();self.assertNotIn('role',result);self.assertNotIn('email',result)
    def test_invalid_sdk_session_denied(self):
        with self.assertRaises(Problem):self.auth(signed=False)
    def test_wrong_issuer_origin_and_machine_identity_denied(self):
        for key,value in [('iss','https://wrong.test'),('azp','https://hostile.test'),('sub','machine_123'),('sid','')]:
            with self.subTest(key=key),self.assertRaises(Problem):self.auth(CLAIMS|{key:value})
    def test_cookie_only_never_authenticates(self):
        with patch('app.identity._sdk_authenticate') as sdk:
            self.assertIsNone(authenticate({'Cookie':'__session=untrusted'},'http://localhost:8080',CONFIG));sdk.assert_not_called()
    def test_sdk_failure_denies_without_error_detail(self):
        with patch('app.identity._sdk_authenticate',side_effect=RuntimeError('secret diagnostic')):
            with self.assertRaises(Problem) as e:authenticate({'Authorization':'Bearer x'},'http://localhost:8080',CONFIG)
            self.assertEqual(e.exception.status,503);self.assertNotIn('secret',e.exception.message)
    def test_configuration_closed(self):
        for update in [{'secret_key':''},{'authorized_parties':[]},{'authorized_parties':['https://*.example.test']},{'mode':'unknown'}]+[{'issuer':value} for value in ['https://identity.test:8080','https://*.test','https://identity.test/path','https://identity.test;unsafe','https://identité.test','https://identity.test\n','https://user'+chr(64)+'identity.test']]:
            with self.subTest(update=update):
                with self.assertRaises(Problem):validate_config(CONFIG|update)
        self.assertNotIn('secret_key',public_config(CONFIG))
        self.assertEqual(public_config(CONFIG)['issuer'],CONFIG['issuer'])
        self.assertEqual(public_config(CONFIG)['authorized_parties'],CONFIG['authorized_parties'])
    def test_v2_org_claim_and_explicit_personal_context(self):
        base={k:v for k,v in CLAIMS.items() if k!='org_id'}
        self.assertEqual(self.auth(base|{'o':{'id':'org_fixture'},'v':2})['org_id'],'org_fixture')
        self.assertEqual(self.auth(CLAIMS|{'o':{'id':'org_fixture'},'v':2})['org_id'],'org_fixture')
        self.assertEqual(self.auth(base)['org_id'],'')
        for update in [{'org_id':None},{'org_id':''},{'org_id':0},{'o':{}},{'o':None},{'o':[]},{'o':{'id':''}},{'o':{'id':17}},{'o':{'id':'org_other'},'org_id':'org_fixture'}]:
            with self.subTest(update=update),self.assertRaises(Problem):self.auth(base|update)
    @unittest.skipUnless(importlib.util.find_spec('clerk_backend_api'),'Optional official SDK not installed')
    def test_official_sdk_invalid_token_fails_closed(self):
        # Actual installed SDK runs here. No live account or successful JWT is claimed.
        with self.assertRaises(Problem) as e:
            authenticate({'Authorization':'Bearer malformed-token'},'http://localhost:8080/api/session',CONFIG)
        self.assertEqual(e.exception.status,401)
    def test_explicit_membership_not_email_or_token_role(self):
        c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
        c.executescript('CREATE TABLE users(id,name,email,role,organization_id); CREATE TABLE external_identities(provider,issuer,subject,user_id,organization_id,external_organization_id,state);')
        c.execute("INSERT INTO users VALUES('local','Name','user@demo.invalid','investor','tenant')")
        with self.assertRaises(Problem):resolve_user(c,CLAIMS)
        c.execute('INSERT INTO external_identities VALUES(?,?,?,?,?,?,?)',('clerk',CONFIG['issuer'],'user_fixture','local','tenant','org_fixture','ACTIVE'))
        self.assertEqual(resolve_user(c,CLAIMS)['role'],'investor')
        with self.assertRaises(Problem):resolve_user(c,CLAIMS|{'org_id':'org_other'})
        c.execute("UPDATE users SET organization_id='other'")
        with self.assertRaises(Problem):resolve_user(c,CLAIMS)
        c.execute("UPDATE users SET organization_id='tenant'");c.execute("UPDATE external_identities SET state='REVOKED'")
        with self.assertRaises(Problem):resolve_user(c,CLAIMS)
        c.close()

if __name__=='__main__':unittest.main()

