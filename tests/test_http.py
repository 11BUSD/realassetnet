import concurrent.futures, http.cookiejar, json, tempfile, threading, unittest, urllib.request, urllib.error
from contextlib import closing
from pathlib import Path
from server import make_server
from app.core import connect,integrity
from app.service import seed_demo

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.db=Path(cls.tmp.name)/'http.sqlite';cls.server=make_server(cls.db,0)
        with closing(connect(cls.db)) as c:seed_demo(c);c.commit()
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def request(self,path,data=None,headers=None,client=None):
        h={'Content-Type':'application/json'}|(headers or {})
        req=urllib.request.Request(self.url+path,json.dumps(data).encode() if data is not None else None,h)
        try:
            response=(client or urllib.request.build_opener()).open(req);body=response.read();return response.status,json.loads(body) if response.headers.get_content_type()=='application/json' else body,response.headers
        except urllib.error.HTTPError as e:return e.code,json.loads(e.read()),e.headers
    def client(self,role):
        client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        status,body,headers=self.request('/api/login',{'email':role+'@demo.invalid','password':'DemoOnly!2026'},client=client)
        self.assertEqual(status,200);return client,body['csrf']
    def test_csrf_and_origin(self):
        client,csrf=self.client('broker')
        code,_,_=self.request('/api/properties',{},client=client);self.assertEqual(code,403)
        code,_,_=self.request('/api/properties',{},headers={'X-CSRF-Token':csrf,'Origin':'https://hostile.example'},client=client);self.assertEqual(code,403)
    def test_public_boundary_and_static_allowlist(self):
        code,body,h=self.request('/api/properties');self.assertEqual(code,200);self.assertEqual(len(body['properties']),3)
        for p in body['properties']:self.assertNotIn('claims',p)
        for path in ['/runtime/app.sqlite','/../private/sample.sqlite','/app/core.py']:
            self.assertEqual(self.request(path)[0],404)
        self.assertIn("object-src 'none'",h['Content-Security-Policy'])
    def test_session_cookie_flags_and_host(self):
        code,b,h=self.request('/api/login',{'email':'investor@demo.invalid','password':'DemoOnly!2026'})
        self.assertIn('HttpOnly',h['Set-Cookie']);self.assertIn('SameSite=Strict',h['Set-Cookie'])
        self.assertEqual(self.request('/api/properties',headers={'Host':'attacker.example'})[0],403)
    def test_private_room_requires_explicit_grant(self):
        client,_=self.client('investor');pid=self.request('/api/properties')[1]['properties'][0]['id']
        self.assertEqual(self.request(f'/api/properties/{pid}/room',client=client)[0],403)
    def test_parallel_audit_appends_remain_consistent(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(lambda _:self.request('/api/properties')[0],range(10)))
        self.assertEqual(results,[200]*10)
        with closing(connect(self.db)) as c:self.assertTrue(integrity(c))

if __name__=='__main__':unittest.main()
