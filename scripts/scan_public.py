"""Conservative, local-only publication boundary check. Never scans the parent workspace."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = {'api', 'app', 'web', 'tests', 'fixtures', 'migrations', 'docs', 'scripts', 'skills', '.github'}
ROOT_FILES = {'server.py', 'README.md', 'Dockerfile', '.dockerignore', '.gitignore', '.env.example', 'factory_manifest.json','requirements-identity.txt','vercel.json'}
IGNORED = {'runtime', '.git', '__pycache__', '.pytest_cache', '.venv'}
DATABASE_EXTENSIONS = {'.sqlite', '.sqlite3', '.db', '.mdb', '.accdb', '.xlsx', '.xls', '.parquet'}
PRIVATE_FILES = {'seed' + '.py', 'network' + '.py', 'build_' + 'database.py', 'review_' + 'data.json'}
PRIVATE_NAMES = ['C' + 'BRE', 'Coll' + 'iers', 'Quad' + 'Real', 'Peakhill' + ' Capital', 'Harley' + ' Gold', 'Knight' + ' Frank', 'Michael' + ' Betsalel', 'Fiera' + ' Real Estate']
EMAIL = re.compile(r'(?<![\w.-])[A-Z0-9][A-Z0-9.!#$%&\x27*+/=?^_`{|}~-]*@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])', re.I)
SECRETS = [re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'), re.compile(r'AKIA[0-9A-Z]{16}'), re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}'), re.compile(r'sk-[A-Za-z0-9_-]{32,}')]

def intended_files(root):
    files, findings = [], []
    def unsafe_link(path):
        # Windows junctions are reparse points but need not report is_symlink().
        attributes=getattr(os.lstat(path),'st_file_attributes',0)
        return path.is_symlink() or bool(attributes & 0x400) or not path.resolve().is_relative_to(root)
    def walk(directory):
        for path in sorted(directory.iterdir()):
            relative = path.relative_to(root).as_posix()
            if unsafe_link(path):
                findings.append({'path': relative, 'rule': 'SYMLINK_NOT_PUBLIC'}); continue
            if path.name in IGNORED: continue
            if path.is_dir(): walk(path)
            elif path.is_file(): files.append(path)
    for path in sorted(root.iterdir()):
        if unsafe_link(path):
            findings.append({'path': path.name, 'rule': 'SYMLINK_NOT_PUBLIC'}); continue
        if path.name in IGNORED: continue
        if path.is_dir() and path.name in DIRECTORIES: walk(path)
        elif path.is_file() and path.name in ROOT_FILES: files.append(path)
        else: findings.append({'path': path.name, 'rule': 'NOT_IN_PUBLIC_ALLOWLIST'})
    return files, findings

def scan(root=ROOT):
    root = root.resolve()
    files, findings = intended_files(root)
    manifest = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() in DATABASE_EXTENSIONS or path.name in PRIVATE_FILES or (path.name.startswith('.env') and path.name != '.env.example'):
            findings.append({'path': relative, 'rule': 'PRIVATE_DATA_OR_CONFIGURATION'}); continue
        data = path.read_bytes()
        if data.startswith(b'SQLite format 3'):
            findings.append({'path': relative, 'rule': 'DATABASE_MAGIC'}); continue
        try: content = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            findings.append({'path': relative, 'rule': 'BINARY_REQUIRES_EXPLICIT_PUBLIC_REVIEW'}); continue
        if '\x00' in content: findings.append({'path': relative, 'rule': 'BINARY_CONTENT'})
        if any(p.search(content) for p in SECRETS): findings.append({'path': relative, 'rule': 'CREDENTIAL_PATTERN'})
        if any(not e.lower().endswith('@demo.invalid') for e in EMAIL.findall(content)):
            findings.append({'path': relative, 'rule': 'NON_SYNTHETIC_EMAIL'})
        if any(re.search(r'\b'+re.escape(name)+r'\b',content,re.I) for name in PRIVATE_NAMES):
            findings.append({'path': relative, 'rule': 'PRIVATE_RESEARCH_CANARY'})
        if re.search(r'(?:C:[/\\]RealAssetNet[/\\](?:data|outputs)|\.\.[/\\](?:data|outputs)[/\\])',content,re.I):
            findings.append({'path': relative, 'rule': 'PRIVATE_WORKSPACE_PATH'})
        manifest.append({'path': relative, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
    # Detect accidentally tracked runtime/secrets without enumerating a parent repository.
    try:
        top=subprocess.run(['git','-C',str(root),'rev-parse','--show-toplevel'],capture_output=True,text=True,timeout=10)
        if top.returncode==0 and Path(top.stdout.strip()).resolve()==root:
            tracked=subprocess.run(['git','-C',str(root),'ls-files','-z'],capture_output=True,timeout=10,check=True)
            approved={entry['path'] for entry in manifest}
            for raw in tracked.stdout.split(b'\x00'):
                if raw and raw.decode('utf-8') not in approved:
                    findings.append({'path': raw.decode('utf-8'), 'rule': 'TRACKED_OUTSIDE_PUBLIC_MANIFEST'})
    except (OSError,subprocess.SubprocessError,UnicodeError) as exc:
        if (root/'.git').exists(): findings.append({'path': '.', 'rule': 'GIT_INSPECTION_UNAVAILABLE', 'detail': type(exc).__name__})
    return {'schema_version':'1.0.0','root':str(root),'passed':not findings,'files_checked':len(files),'findings':findings,'manifest':manifest,'limits':['Pattern checks cannot prove absence of all confidential data. Human review of the exact publication diff is required.','Only the project allowlist is scanned; excluded runtime is never an export target.']}

def self_test():
    cases=4;link_case='not_available'
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);(root/'docs').mkdir();(root/'runtime').mkdir()
        target=root/'docs'/'sample.md';target.write_text('Person <broker@demo.invalid>',encoding='utf-8')
        (root/'runtime'/'private.db').write_bytes(b'SQLite format 3\x00')
        assert scan(root)['passed'], 'Synthetic files and excluded runtime should pass'
        target.write_text('person' + '@example.org',encoding='utf-8')
        assert any(f['rule']=='NON_SYNTHETIC_EMAIL' for f in scan(root)['findings'])
        target.write_text('SYNTHETIC',encoding='utf-8'); (root/'docs'/'leak.txt').write_bytes(b'SQLite format 3\x00')
        assert any(f['rule']=='DATABASE_MAGIC' for f in scan(root)['findings'])
        (root/'docs'/'leak.txt').unlink(); (root/'private.csv').write_text('unexpected',encoding='utf-8')
        assert any(f['rule']=='NOT_IN_PUBLIC_ALLOWLIST' for f in scan(root)['findings'])
        (root/'private.csv').unlink();target.write_text('-----BEGIN ' + 'PRIVATE KEY-----',encoding='utf-8')
        assert any(f['rule']=='CREDENTIAL_PATTERN' for f in scan(root)['findings'])
        target.write_text(PRIVATE_NAMES[0],encoding='utf-8')
        assert any(f['rule']=='PRIVATE_RESEARCH_CANARY' for f in scan(root)['findings'])
        target.write_bytes(b'\xff\xfe')
        assert any(f['rule']=='BINARY_REQUIRES_EXPLICIT_PUBLIC_REVIEW' for f in scan(root)['findings'])
        target.write_text('synthetic',encoding='utf-8');db=root/'docs'/'synthetic.sqlite';db.write_text('synthetic',encoding='utf-8')
        assert any(f['rule']=='PRIVATE_DATA_OR_CONFIGURATION' for f in scan(root)['findings'])
        db.unlink();cases+=4
        link=root/'docs'/'escape'
        try: link.symlink_to(root/'runtime',target_is_directory=True)
        except OSError: pass
        else:
            assert any(f['rule']=='SYMLINK_NOT_PUBLIC' for f in scan(root)['findings'])
            link.unlink();cases+=1;link_case='passed'
    return {'self_test':'passed','cases':cases,'symlink_case':link_case}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    if args.self_test: print(json.dumps(self_test())); raise SystemExit(0)
    result=scan();print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)
