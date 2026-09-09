"""Local operator scanner. The HTTP server never receives a Docker socket or runs containers."""
import hashlib,json,re,secrets,subprocess,tempfile,threading
from datetime import datetime,timezone,timedelta
from pathlib import Path
from .core import Problem,require,ROOT

def isolation(image,input_path,entrypoint=None):
    require(re.fullmatch(r'sha256:[0-9a-f]{64}',image),'Scanner/parser must be pinned to a local image ID')
    require(input_path.is_file(),'Input file missing')
    require(',' not in str(input_path),'Input path contains unsupported mount delimiter')
    args=['docker','run','--rm','--name','ran-doc-'+secrets.token_hex(10),'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','65534:65534','--memory','4g','--cpus','1','--pids-limit','64','--tmpfs','/tmp:rw,noexec,nosuid,size=128m','--mount',f'type=bind,source={input_path.resolve()},target=/input/document,readonly']
    if entrypoint:args+=['--entrypoint',entrypoint]
    return args+[image]
def run_limited(command,timeout=120):
    name=command[command.index('--name')+1];chunks=[];exceeded=threading.Event()
    p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,shell=False)
    def collect():
        size=0
        while True:
            chunk=p.stdout.read(65536)
            if not chunk:break
            size+=len(chunk)
            if size>8000000:exceeded.set();p.kill();break
            chunks.append(chunk)
    reader=threading.Thread(target=collect,daemon=True);reader.start()
    try:
        try:p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:p.kill();p.wait();raise Problem('Document process timed out; quarantine retained',503)
        reader.join(timeout=5);require(not exceeded.is_set(),'Worker output limit exceeded',503)
        return p.returncode,b''.join(chunks).decode('utf-8',errors='replace')
    finally:
        # Terminate the container itself, not merely the attached Docker client, on all paths.
        subprocess.run(['docker','rm','--force',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
        if p.stdout:p.stdout.close()
def process_file(path,config_path=None):
    source=Path(path).resolve(strict=True)
    require(source.is_file() and source.stat().st_size<=25000000,"Input exceeds document limit")
    data=source.read_bytes()
    require(len(data)<=25000000,"Input exceeds document limit")
    with tempfile.TemporaryDirectory(prefix="ran-document-") as folder:
        snapshot=Path(folder)/("document"+source.suffix.lower())
        snapshot.write_bytes(data)
        report=_process_snapshot(snapshot,config_path)
        require(hashlib.sha256(source.read_bytes()).hexdigest()==report["source_sha256"],"Source changed during processing; results rejected",409)
        return report

def _process_snapshot(path,config_path=None):
    config_path=Path(config_path or ROOT/'runtime/document-processing.json')
    require(config_path.exists(),'Isolated document processing is not configured',503)
    cfg=json.loads(config_path.read_text());source=Path(path).resolve(strict=True)
    require(source.is_file() and source.stat().st_size<=25000000,'Input exceeds document limit')
    require(source.suffix.lower() in ['.pdf','.csv','.xlsx','.numbers'],'Unsupported review format',415)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    # A fresh explicit signature timestamp is checked before every scan; old data never passes as current.
    verified=datetime.fromisoformat(cfg['signature_date'])
    require(timedelta(0)<=datetime.now(timezone.utc)-verified<=timedelta(days=7),'Antivirus signatures are stale; refresh scanner image',503)
    code,scan=run_limited(isolation(cfg['scanner_image'],source,'clamscan')+['--no-summary','--max-filesize=25M','--max-scansize=64M','--max-recursion=15','--alert-exceeds-max=yes','--alert-encrypted=yes','/input/document'])
    report={'source_sha256':digest,'byte_length':source.stat().st_size,'scanned_at':datetime.now(timezone.utc).isoformat(),'scanner_image':cfg['scanner_image'],'signature_date':cfg['signature_date'],'scanner_exit_code':code,'scan_status':'NO_KNOWN_THREAT_DETECTED' if code==0 and '/input/document: OK' in scan else 'QUARANTINED','parser_image':cfg['parser_image'],'network':'NONE','source_mount':'READ_ONLY','scan_log':scan[:2000]}
    if report['scan_status']!='NO_KNOWN_THREAT_DETECTED':return report
    code,parsed=run_limited(isolation(cfg['parser_image'],source)+[source.suffix.lower()])
    require(hashlib.sha256(source.read_bytes()).hexdigest()==digest,'Source changed during processing; results rejected',409)
    try:payload=json.loads(parsed)
    except ValueError:payload={'ok':False,'error':'Invalid worker response'}
    report['extraction_status']='PROPOSED_UNVERIFIED' if code==0 and payload.get('ok') else 'FAILED'
    if payload.get('ok'):report['extraction']=payload['result']
    else:report['extraction_error']=payload
    return report
