"""Pin installed scanner/parser images and capture actual signature age; no uploads during setup."""
import json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
def output(args):return subprocess.check_output(args,text=True,timeout=30).strip()
scanner=output(['docker','image','inspect','clamav/clamav:stable','--format','{{.Id}}'])
parser=output(['docker','image','inspect','realassetnet-document-reader:local','--format','{{.Id}}'])
version=output(['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','65534:65534','--entrypoint','clamscan',scanner,'--version'])
date=datetime.strptime(version.rsplit('/',1)[1],'%a %b %d %H:%M:%S %Y').replace(tzinfo=timezone.utc)
cfg={'scanner_image':scanner,'parser_image':parser,'signature_date':date.isoformat(),'scanner_version':version}
(ROOT/'runtime').mkdir(exist_ok=True);(ROOT/'runtime/document-processing.json').write_text(json.dumps(cfg,indent=2))
print(json.dumps({'configured':True,'scanner_version':version,'signatures':date.isoformat(),'network_during_document_processing':'NONE'}))
