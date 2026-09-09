"""Configure an external private research source locally; never print the operator key."""
import argparse
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.private_network import external_database, read_connection, Problem

def configure(database,config_path=None,key_path=None,public_root=ROOT):
    source=external_database(database,public_root)
    connection=read_connection(source,public_root)
    connection.close()
    config_path=Path(config_path) if config_path else ROOT/'runtime'/'private-network.json'
    key_path=Path(key_path) if key_path else ROOT/'runtime'/'operator.key'
    require_runtime=Path(public_root).resolve()/'runtime'
    if not config_path.resolve().is_relative_to(require_runtime) or not key_path.resolve().is_relative_to(require_runtime): raise Problem('Private configuration and key must stay in excluded runtime',400)
    if config_path.exists() or key_path.exists(): raise Problem('Private configuration already exists; preserve or explicitly rotate it before reconfiguration',409)
    config_path.parent.mkdir(parents=True,exist_ok=True);key_path.parent.mkdir(parents=True,exist_ok=True)
    key=secrets.token_urlsafe(48)
    config={'version':1,'database':str(source),'operator_key_sha256':hashlib.sha256(key.encode()).hexdigest()}
    # Exclusive creation avoids overwriting existing operator credentials.
    key_fd=os.open(key_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(key_fd,'w',encoding='utf-8') as stream: stream.write(key+'\n')
    try:
        config_fd=os.open(config_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(config_fd,'w',encoding='utf-8') as stream: json.dump(config,stream,indent=2)
    except Exception:
        key_path.unlink();raise
    return {'configured':True,'mode':'PRIVATE_READ_ONLY','key_printed':False,'configuration_saved_in_runtime':True}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--database',required=True);args=parser.parse_args()
    try: print(json.dumps(configure(args.database)))
    except (Problem,OSError) as error:
        print(error.message if isinstance(error,Problem) else 'Private network configuration could not be written',file=sys.stderr);raise SystemExit(1)
