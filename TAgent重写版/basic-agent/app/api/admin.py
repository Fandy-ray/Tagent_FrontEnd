from flask import Blueprint, jsonify

from app.errors.api_errors import AgentAPIError
from app.api.deps import get_registry, invalidate_provider
from app.api.security import require_admin_token
from app.api.validators import json_body


blueprint = Blueprint("admin", __name__, url_prefix="/admin/model-providers")


@blueprint.get("")
def list_providers():
    require_admin_token()
    return jsonify(get_registry().public_registry())


@blueprint.post("")
def create_provider():
    require_admin_token()
    try:
        provider = get_registry().create_provider(json_body())
    except ValueError as exc:
        raise AgentAPIError(str(exc), 400, "validation_error") from exc
    invalidate_provider(provider["served_model_id"])
    return jsonify(provider), 201


@blueprint.put("/<string:served_model_id>")
def update_provider(served_model_id: str):
    require_admin_token()
    try:
        provider = get_registry().update_provider(served_model_id, json_body())
    except KeyError as exc:
        raise AgentAPIError("Model provider not found.", 404, "model_not_found") from exc
    except ValueError as exc:
        raise AgentAPIError(str(exc), 400, "validation_error") from exc
    invalidate_provider(served_model_id)
    return jsonify(provider)


@blueprint.delete("/<string:served_model_id>")
def delete_provider(served_model_id: str):
    require_admin_token()
    try:
        get_registry().delete_provider(served_model_id)
    except KeyError as exc:
        raise AgentAPIError("Model provider not found.", 404, "model_not_found") from exc
    invalidate_provider(served_model_id)
    return jsonify({"status": True, "default_model_id": get_registry().get_default_model_id()})


@blueprint.post("/default")
def set_default_provider():
    require_admin_token()
    data = json_body()
    served_model_id = data.get("served_model_id")
    if not isinstance(served_model_id, str) or not served_model_id:
        raise AgentAPIError("served_model_id is required.", 400, "validation_error")
    try:
        result = get_registry().set_default_model(served_model_id)
    except KeyError as exc:
        raise AgentAPIError("Model provider not found or disabled.", 404, "model_not_found") from exc
    return jsonify(result)
