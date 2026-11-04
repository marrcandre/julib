"""Encrypted PostgreSQL and managed-cover backup. Run only from private operations repository."""
import argparse
import io
import json
import os
from pathlib import Path
import secrets
import struct
import subprocess
import tarfile
from datetime import datetime, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b'JULIB01'

def keypair() -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    return (key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()), key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))

def encrypt(data: bytes, public_pem: bytes) -> bytes:
    key=secrets.token_bytes(32);nonce=secrets.token_bytes(12)
    public=serialization.load_pem_public_key(public_pem)
    encrypted_key=public.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    return MAGIC+struct.pack('>H',len(encrypted_key))+encrypted_key+nonce+AESGCM(key).encrypt(nonce,data,MAGIC)

def decrypt(data: bytes, private_pem: bytes) -> bytes:
    if not data.startswith(MAGIC):raise ValueError('Formato de backup inválido.')
    size=struct.unpack('>H',data[7:9])[0];offset=9+size
    private=serialization.load_pem_private_key(private_pem,password=None)
    key=private.decrypt(data[9:offset],padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    return AESGCM(key).decrypt(data[offset:offset+12],data[offset+12:],MAGIC)

def add_bytes(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o600
    archive.addfile(info,io.BytesIO(data))

def backup(output: Path, public_key: Path, with_media: bool) -> None:
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
    import django
    django.setup()
    from library.models import Book
    database=os.environ['BACKUP_DATABASE_URL']
    dump=subprocess.run(['pg_dump',database,'--schema=public','--format=custom','--no-owner','--no-acl'],check=True,capture_output=True).stdout
    manifest={'created_at':datetime.now(timezone.utc).isoformat(),'format':1,'media':[]}
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w:gz') as archive:
        add_bytes(archive,'database.dump',dump)
        if with_media:
            from library.media import configure
            import cloudinary.api
            import httpx
            configure()
            for i, public_id in enumerate(Book.objects.exclude(cover_id='').values_list('cover_id',flat=True).distinct()):
                resource=cloudinary.api.resource(public_id)
                response=httpx.get(resource['secure_url'],timeout=30);response.raise_for_status()
                name=f'media/{i}.{resource["format"]}'
                add_bytes(archive,name,response.content)
                manifest['media'].append({'public_id':public_id,'file':name})
        add_bytes(archive,'manifest.json',json.dumps(manifest).encode())
    result=encrypt(buffer.getvalue(),public_key.read_bytes())
    limit=int(os.environ.get('BACKUP_MAX_BYTES',str(50*1024*1024)))
    if len(result)>limit:raise SystemExit('Backup excede o orçamento configurado. Nada foi enviado; revise capacidade e destino.')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(result);output.chmod(0o600)
    print(f'Backup cifrado criado: {len(result)} bytes. Verifique a retenção privada de sete dias.')

def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    key=sub.add_parser('keygen');key.add_argument('--private',type=Path,required=True);key.add_argument('--public',type=Path,required=True)
    create=sub.add_parser('create');create.add_argument('--public',type=Path,required=True);create.add_argument('--output',type=Path,required=True);create.add_argument('--media',action='store_true')
    restore=sub.add_parser('decrypt');restore.add_argument('--private',type=Path,required=True);restore.add_argument('--input',type=Path,required=True);restore.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='keygen':
        if args.private.exists() or args.public.exists():raise SystemExit('Não sobrescrever chaves existentes.')
        private,public=keypair();args.private.write_bytes(private);args.private.chmod(0o600);args.public.write_bytes(public)
    elif args.command=='create':backup(args.output,args.public,args.media)
    else:
        if args.output.exists():raise SystemExit('Destino de recuperação já existe.')
        args.output.write_bytes(decrypt(args.input.read_bytes(),args.private.read_bytes()));args.output.chmod(0o600)

if __name__=='__main__':main()
