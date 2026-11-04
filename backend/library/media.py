import os
import time
from typing import Any
import cloudinary
import cloudinary.utils
import cloudinary.api
from django.core.exceptions import ValidationError
from .models import Library


def configure() -> None:
    if not all(os.environ.get(k) for k in ('CLOUDINARY_CLOUD_NAME','CLOUDINARY_API_KEY','CLOUDINARY_API_SECRET')):
        raise ValidationError('Upload não configurado. Defina as credenciais Cloudinary no servidor.')
    cloudinary.config(cloud_name=os.environ['CLOUDINARY_CLOUD_NAME'], api_key=os.environ['CLOUDINARY_API_KEY'], api_secret=os.environ['CLOUDINARY_API_SECRET'], secure=True)


def signature(library: Library) -> dict[str, Any]:
    configure()
    params = {'timestamp': int(time.time()), 'folder':f'julib/{library.pk}', 'allowed_formats':'jpg,jpeg,png,webp', 'transformation':'c_limit,w_1200,h_1800/q_auto,f_auto', 'overwrite':'false'}
    return {**params, 'signature':cloudinary.utils.api_sign_request(params, os.environ['CLOUDINARY_API_SECRET']), 'api_key':os.environ['CLOUDINARY_API_KEY'], 'cloud_name':os.environ['CLOUDINARY_CLOUD_NAME']}


def verify_upload(library: Library, public_id: str) -> dict[str, str]:
    configure()
    if not public_id.startswith(f'julib/{library.pk}/'):
        raise ValidationError('Imagem não pertence à biblioteca.')
    resource = cloudinary.api.resource(public_id)
    if resource.get('format') not in {'jpg','jpeg','png','webp','avif'} or resource.get('bytes',0) > 5*1024*1024:
        raise ValidationError('Imagem inválida ou maior que 5 MB.')
    return {'cover_id':public_id, 'cover_url':resource['secure_url']}
