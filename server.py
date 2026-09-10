"""Dependency-free local simulation server. Not an internet production deployment server."""
import argparse, hashlib, json, mimetypes, os, secrets, sqlite3, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit
from app.core import *
from app.service import dispatch, seed_demo
from app.private_network import handle as private_network_handle
from app import identity
from app.providers import provider_status,ingest_event

RATE={}
class Handler(BaseHTTPRequestHandler):
    server_version='RealassetnetSimulation'
    def log_message(self, format, *args): pass # Do not log document contents, cookies or credentials.
    def respond(self,status,body,ctype='application/json',cookie=None):
        raw=body if isinstance(body,bytes) else js(body).encode()
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY')
        config=self.server.identity_config
        clerk=config['issuer'].rstrip('/') if config['mode']=='clerk' else ''
        extra=f' {clerk} https://challenges.cloudflare.com' if clerk else ''
        images=' https://img.clerk.com' if clerk else ''
        self.send_header('Content-Security-Policy',f"default-src 'self'; script-src 'self'{extra}; style-src 'self' 'unsafe-inline'; img-src 'self' data:{images}; connect-src 'self'{extra}; frame-src 'self'{extra}; worker-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'{extra}")
        self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()')
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(raw)
    def do_GET(self): self.handle_request('GET')
    def do_POST(self): self.handle_request('POST')
    def configure_serverless_runtime(self):
        """Initialize the ephemeral Vercel demo runtime on its first invocation.

        The regular local server sets these attributes in ``make_server``. Vercel
        instantiates the request handler directly, so it needs the same explicit,
        fail-closed configuration here. Durable production state must use a
        managed database; this only makes the existing simulation usable for a
        short-lived demo instance.
        """
        if hasattr(self.server,'db_path'): return
        db=os.environ.get('RAN_DB','/tmp/realassetnet-simulation.sqlite')
        migrate(db);self.server.db_path=db
        self.server.identity_config=identity.validate_config(identity.load_config())
        # The deployed experience is explicitly a simulation. Seed only the
        # fictional fixtures so the documented demo accounts can sign in on a
        # fresh ephemeral Vercel instance; production must use Clerk + durable
        # storage instead.
        if self.server.identity_config['mode']=='demo':
            c=connect(db)
            try: seed_demo(c); c.commit()
            finally: c.close()
        configured={x.strip() for x in os.environ.get('RAN_ALLOWED_HOSTS','').split(',') if x.strip()}
        # Vercel exposes both the immutable deployment hostname and the stable
        # production alias.  Permit only the exact platform-provided values.
        for env_name in ('VERCEL_URL','VERCEL_BRANCH_URL','VERCEL_PROJECT_PRODUCTION_URL'):
            vercel_host=os.environ.get(env_name,'').strip()
            if vercel_host: configured.add(vercel_host)
        # There is no insecure wildcard fallback: Vercel supplies VERCEL_URL.
        self.server.allowed_hosts=configured or {'localhost:8080','127.0.0.1:8080'}
    def handle_request(self,method):
        path=urlsplit(self.path).path
        c=None;u=None
        try:
            self.configure_serverless_runtime()
            host=self.headers.get('Host','')
            require(host in self.server.allowed_hosts,'Host not allowed',403)
            if not path.startswith('/api/'):
                require(method=='GET','Method not allowed',405)
                files={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/styles.css':'styles.css','/hero-toronto.png':'hero-toronto.png'}
                auth_path=any(path==prefix or path.startswith(prefix+'/') for prefix in ['/auth/sign-in','/auth/sign-up'])
                require(path in files or auth_path,'Not found',404)
                file=ROOT/'web'/('index.html' if auth_path else files[path]);require(file.exists(),'UI is not available',503)
                return self.respond(200,file.read_bytes(),mimetypes.guess_type(file.name)[0] or 'text/plain')
            c=connect(self.server.db_path)
            cookie=SimpleCookie()
            try: cookie.load(self.headers.get('Cookie',''))
            except Exception: pass
            token=cookie['ran_session'].value if 'ran_session' in cookie else ''
            config=self.server.identity_config
            if path=='/api/auth/config' and method=='GET':return self.respond(200,identity.public_config(config))
            provider_callback=path=='/api/providers/events/signed_review_bridge' and method=='POST'
            if config['mode']=='clerk':
                require(path not in ['/api/login','/api/signup','/api/logout'],'Local demo authentication is disabled in Clerk mode',403)
                claims=None if provider_callback else identity.authenticate(self.headers,'http://'+host+self.path,config)
                u,csrf=identity.resolve_user(c,claims),None
            else:u,csrf=session(c,token)
            # Serialize audit append with the associated read/write to prevent hash-chain forks.
            c.execute('BEGIN IMMEDIATE')
            d={}
            if method=='POST':
                require(self.headers.get('Content-Type','').split(';')[0]=='application/json','JSON required',415)
                # TLS terminates at Vercel before the request reaches this
                # Python handler. Compare Origin to the browser-visible scheme,
                # not the internal HTTP hop, while retaining exact host checks.
                forwarded=self.headers.get('X-Forwarded-Proto','').split(',',1)[0].strip().lower()
                scheme=forwarded if forwarded in {'http','https'} else ('http' if host.split(':',1)[0] in {'localhost','127.0.0.1'} else 'https')
                origin=self.headers.get('Origin');require(not origin or origin==scheme+'://'+host,'Cross-origin request rejected',403)
                require(self.headers.get('Sec-Fetch-Site') not in ['cross-site'],'Cross-site request rejected',403)
                limit=7100000 if path.endswith('/upload-binary') else 220000
                length=int(self.headers.get('Content-Length','0'));require(0<length<=limit,'Request exceeds limit or is empty',413)
                raw_body=self.rfile.read(length)
                try: d=json.loads(raw_body,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite number')))
                except (ValueError,UnicodeError): raise Problem('Invalid JSON')
                require(isinstance(d,dict),'JSON object required')
                if path not in ['/api/login','/api/signup'] and not provider_callback:
                    require(u,'Sign in',401)
                    if config['mode']=='demo':require(secrets.compare_digest(self.headers.get('X-CSRF-Token',''),csrf),'CSRF token missing or invalid',403)
            if path=='/api/session' and method=='GET': return self.respond(200,{'user':u,'csrf':csrf,'mode':'SIMULATION_ONLY'})
            if path in ['/api/login','/api/signup'] and method=='POST':
                key=self.client_address[0];window=[x for x in RATE.get(key,[]) if x>time.time()-60];require(len(window)<15,'Too many authentication attempts; wait a minute',429);RATE[key]=window+[time.time()]
                if path=='/api/signup': signup(c,d)
                result,token=login(c,d);c.commit()
                return self.respond(200,result,cookie=f'ran_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
            if path=='/api/logout' and method=='POST':
                c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),));c.commit()
                return self.respond(200,{'ok':True},cookie='ran_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if provider_callback:
                result=ingest_event(c,'signed_review_bridge',raw_body,self.headers)
                audit(c,{'id':'provider:signed_review_bridge','organization_id':None},result['receipt_id'],'PROVIDER_RECEIPT',{'signature_verified':True,'replayed':result['replayed'],'eligibility_changed':False})
            elif path=='/api/providers/status' and method=='GET':
                require(u and u['role']=='admin','Administrator required',403);result=provider_status()
            elif path.startswith('/api/network'):
                result=private_network_handle(c,u,method,path,d,self.headers.get('X-Operator-Key',''))
            else: result=dispatch(c,u,method,path,d)
            c.commit();self.respond(200,result)
        except Problem as e:
            if c:
                # Gateway rolls back its mutations but preserves the denial audit.
                if path=='/api/actions' or path.endswith('/room'): c.commit()
                else:
                    c.rollback()
                    if u and e.status==403:
                        c.execute('BEGIN IMMEDIATE')
                        audit(c,u,'access-control','ACCESS_DENIED',{'path':path,'reason':e.message,'credentials_logged':False})
                        c.commit()
            self.respond(e.status,{'error':e.message})
        except (ValueError,sqlite3.IntegrityError) as e:
            if c:c.rollback()
            self.respond(400,{'error':'Invalid request or conflicting record'})
        except Exception:
            if c:c.rollback()
            import traceback
            print('RAN_UNHANDLED_ERROR',traceback.format_exc(limit=2),flush=True)
            self.respond(500,{'error':'Internal error; no partial transaction committed'})
        finally:
            if c:c.close()

def make_server(path,port=8080,bind='127.0.0.1',identity_config=None):
    migrate(path)
    server=ThreadingHTTPServer((bind,port),Handler);server.db_path=str(path)
    server.identity_config=identity.validate_config(identity_config or identity.load_config())
    actual=server.server_address[1];server.allowed_hosts={f'localhost:{actual}',f'127.0.0.1:{actual}'}
    return server
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8080);parser.add_argument('--bind',default='127.0.0.1');parser.add_argument('--seed-demo',action='store_true');args=parser.parse_args()
    if os.environ.get('RAN_MODE','simulation')!='simulation': raise SystemExit('Only simulation is implemented. Production startup refused.')
    db=os.environ.get('RAN_DB',str(ROOT/'runtime/app.sqlite'));server=make_server(db,args.port,args.bind)
    if args.seed_demo:
        if server.identity_config['mode']!='demo':raise SystemExit('Demo seeding is disabled in Clerk identity mode')
        c=connect(db)
        try:seed_demo(c);c.commit()
        finally:c.close()
    print(f'Realassetnet DEMO/SIMULATION http://localhost:{args.port}',flush=True)
    server.serve_forever()
