"""Local database+artifact backup and verified restore CLI. No cloud account needed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
from app.core.config import get_settings


def connection_env(url):
    from psycopg2.extensions import parse_dsn
    parts=parse_dsn(url)
    mapping={'dbname':'PGDATABASE','host':'PGHOST','hostaddr':'PGHOSTADDR','port':'PGPORT','user':'PGUSER','password':'PGPASSWORD','sslmode':'PGSSLMODE','sslcert':'PGSSLCERT','sslkey':'PGSSLKEY','sslrootcert':'PGSSLROOTCERT','connect_timeout':'PGCONNECT_TIMEOUT','options':'PGOPTIONS'}
    env=dict(os.environ)
    for key,value in parts.items():
        if key in mapping:env[mapping[key]]=value
    return env


def checksum(content):return hashlib.sha256(content).hexdigest()


def verify(path):
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate archive members')
        for name in names:
            p=Path(name)
            if p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe backup member')
        manifest=json.loads(archive.read('manifest.json'))
        declared={item['name'] for item in manifest['files']}
        if declared != set(names)-{'manifest.json'}:raise ValueError('Backup manifest does not cover every member')
        for item in manifest['files']:
            if checksum(archive.read(item['name']))!=item['sha256']:raise ValueError('Backup checksum mismatch')
        if 'database.dump' not in declared:raise ValueError('Backup lacks database dump')
        return manifest


def create(path):
    from app.services.artifacts import bundle
    cfg=get_settings()
    if cfg.ARCHIVE_STORAGE not in ('local','database'):raise ValueError('Back up the remote object bucket separately; this command supports local or database artifacts')
    with tempfile.TemporaryDirectory() as tmp:
        database=Path(tmp)/'database.dump'
        env=connection_env(cfg.DATABASE_URL)
        subprocess.run(['pg_dump','--format=custom','--file',str(database)],env=env,check=True,capture_output=True)
        files={'database.dump':database.read_bytes()}
        root=Path(cfg.ARTIFACT_DIR)
        if cfg.ARCHIVE_STORAGE=='local' and root.exists():
            for item in root.rglob('*'):
                if item.is_file() and not item.is_symlink():files['artifacts/'+str(item.relative_to(root))]=item.read_bytes()
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(bundle(files,{'schema_version':1,'storage':cfg.ARCHIVE_STORAGE,'contains_private_sessions':True}))
        path.chmod(0o600)
    verify(path)


def restore(path,target,artifacts_dir):
    # Refuse restoring over a database with user tables; no destructive clean flag.
    import psycopg2
    verify(path)
    with psycopg2.connect(target) as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p') AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid=c.oid AND d.deptype='e' AND d.refclassid='pg_extension'::regclass)")
            if cursor.fetchone()[0]:raise ValueError('Restore target must be an empty database')
    if artifacts_dir.exists() and any(artifacts_dir.iterdir()):raise ValueError('Restore artifact directory must be empty')
    with tempfile.TemporaryDirectory() as tmp,zipfile.ZipFile(path) as archive:
        database=Path(tmp)/'database.dump';database.write_bytes(archive.read('database.dump'))
        subprocess.run(['pg_restore','--dbname',__import__('psycopg2').extensions.parse_dsn(target)['dbname'],'--no-owner','--no-acl','--exit-on-error','--single-transaction',str(database)],env=connection_env(target),check=True,capture_output=True)
        artifacts_dir.mkdir(parents=True,exist_ok=True)
        for name in archive.namelist():
            if name.startswith('artifacts/'):
                destination=artifacts_dir/Path(name).relative_to('artifacts')
                destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(archive.read(name));destination.chmod(0o600)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('create','verify','restore'):
        command=sub.add_parser(name);command.add_argument('file',type=Path)
        if name=='restore':command.add_argument('--target-env',default='RESTORE_DATABASE_URL');command.add_argument('--artifacts-dir',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.command=='create':create(args.file)
        elif args.command=='verify':verify(args.file)
        else:
            target=os.environ.get(args.target_env)
            if not target:parser.error('Set the target connection string in the named environment variable')
            restore(args.file,target,args.artifacts_dir)
    except subprocess.CalledProcessError:raise SystemExit('Database backup/restore failed; check client/server versions and connection configuration (credentials are not logged)')
    print(f'{args.command.title()} completed: {args.file}')

if __name__=='__main__':main()
