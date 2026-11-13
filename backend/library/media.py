import time
from typing import Any

import cloudinary
import cloudinary.api
import cloudinary.utils
from django.core.exceptions import ValidationError

from .models import Library


def configure() -> Any:
    # Config lê CLOUDINARY_URL ou as variáveis individuais seguindo a precedência do SDK.
    config = cloudinary.Config()
    config.secure = True
    if not all((config.cloud_name, config.api_key, config.api_secret)):
        raise ValidationError(
            "Upload não configurado. Defina as credenciais Cloudinary no servidor."
        )
    return cloudinary.config(**config.__dict__)


def signature(library: Library) -> dict[str, Any]:
    config = configure()
    params = {
        "timestamp": int(time.time()),
        "folder": f"julib/{library.pk}",
        "allowed_formats": "jpg,jpeg,png,webp",
        "transformation": "c_limit,w_1200,h_1800/q_auto,f_auto",
        "overwrite": "false",
    }
    return {
        **params,
        "signature": cloudinary.utils.api_sign_request(params, config.api_secret),
        "api_key": config.api_key,
        "cloud_name": config.cloud_name,
    }


def verify_upload(library: Library, public_id: str) -> dict[str, str]:
    configure()
    if not public_id.startswith(f"julib/{library.pk}/"):
        raise ValidationError("Imagem não pertence à biblioteca.")
    resource = cloudinary.api.resource(public_id)
    canonical_public_id = resource.get("public_id")
    if (
        not isinstance(canonical_public_id, str)
        or canonical_public_id != public_id
        or not canonical_public_id.startswith(f"julib/{library.pk}/")
    ):
        raise ValidationError("O identificador canônico da imagem não pertence à biblioteca.")
    if (
        resource.get("format") not in {"jpg", "jpeg", "png", "webp", "avif"}
        or resource.get("bytes", 0) > 5 * 1024 * 1024
    ):
        raise ValidationError("Imagem inválida ou maior que 5 MB.")
    return {"cover_id": public_id, "cover_url": resource["secure_url"]}
