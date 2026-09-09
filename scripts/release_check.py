"""Produce local release evidence. Does not deploy, publish, commit, or merge."""
import hashlib
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from scan_public import ROOT, scan, self_test
sys.path.insert(0,str(ROOT))

def main():
    runtime=ROOT/'runtime';runtime.mkdir(exist_ok=True)
    self_test()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),top_level_dir=str(ROOT/'tests'))
    count=suite.countTestCases()
    if not count: raise SystemExit('No tests discovered; release gate cannot pass.')
    test=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True,timeout=180)
    log=test.stdout+test.stderr;(runtime/'release_tests.log').write_text(log,encoding='utf-8')
    print(log)
    public=scan()
    (runtime/'public_scan.json').write_text(json.dumps(public,indent=2),encoding='utf-8')
    digest=hashlib.sha256(json.dumps(public['manifest'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    evidence={'schema_version':'1.0.0','timestamp':datetime.now(timezone.utc).isoformat(),'candidate':'local-simulation-only','passed':test.returncode==0 and public['passed'],'test_count':count,'tests_exit_code':test.returncode,'tests_log_sha256':hashlib.sha256(log.encode()).hexdigest(),'public_scan_passed':public['passed'],'public_scan_findings':public['findings'],'source_manifest_sha256':digest,'source_manifest':public['manifest'],'deployment_authorized':False,'production_ready':False,'remaining_gates':['Human review of exact publication diff','Independent security review','Production legal and operational qualification','Production hosting and provider integration']}
    path=runtime/'release_evidence.json';path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps({'passed':evidence['passed'],'evidence':str(path),'public_findings':public['findings']},indent=2))
    return 0 if evidence['passed'] else 1

if __name__=='__main__': raise SystemExit(main())
