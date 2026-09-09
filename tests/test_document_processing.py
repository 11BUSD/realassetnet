import tempfile,json,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from app.document_processing import process_file,isolation
from app.core import Problem
class DocumentIsolationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.source=self.root/'source.csv';self.source.write_text('a,b\n1,2');self.cfg=self.root/'config.json';self.cfg.write_text(json.dumps({'scanner_image':'sha256:'+'a'*64,'parser_image':'sha256:'+'b'*64,'signature_date':datetime.now(timezone.utc).isoformat()}))
 def test_isolation_has_no_network_and_readonly_source(self):
  cmd=isolation('sha256:'+'a'*64,self.source)
  for value in ['none','--read-only','ALL','no-new-privileges','65534:65534','--memory','--pids-limit']:self.assertIn(value,cmd)
  self.assertTrue(any('target=/input/document,readonly' in x for x in cmd))
  with self.assertRaises(Problem):isolation('latest',self.source)
 def test_detected_threat_never_reaches_parser(self):
  with patch('app.document_processing.run_limited',return_value=(1,'FOUND')) as run:
   self.assertEqual(process_file(self.source,self.cfg)['scan_status'],'QUARANTINED');self.assertEqual(run.call_count,1)
 def test_stale_signatures_fail_before_execution(self):
  cfg=json.loads(self.cfg.read_text());cfg['signature_date']=(datetime.now(timezone.utc)-timedelta(days=8)).isoformat();self.cfg.write_text(json.dumps(cfg))
  with patch('app.document_processing.run_limited') as run:
   with self.assertRaises(Problem):process_file(self.source,self.cfg)
   run.assert_not_called()
 def test_scanner_and_parser_share_private_snapshot(self):
  mounts=[]
  def run(cmd):
   mounts.append(cmd[cmd.index('--mount')+1]);return (0,'/input/document: OK') if len(mounts)==1 else (0,'{"ok":true,"result":{"rows":1}}')
  with patch('app.document_processing.run_limited',side_effect=run):self.assertEqual(process_file(self.source,self.cfg)['extraction_status'],'PROPOSED_UNVERIFIED')
  self.assertEqual(mounts[0],mounts[1]);self.assertNotIn(str(self.source),mounts[0])
 def test_changed_original_rejects_review(self):
  def run(cmd):
   self.source.write_text('changed');return (0,'/input/document: OK') if 'clamscan' in cmd else (0,'{"ok":true,"result":{}}')
  with patch('app.document_processing.run_limited',side_effect=run):
   with self.assertRaises(Problem):process_file(self.source,self.cfg)
