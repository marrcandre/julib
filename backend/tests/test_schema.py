from library.api import api


def test_openapi_exposes_typed_catalog_contract():
    schema = api.get_openapi_schema()
    response = schema["paths"]["/api/v1/books"]["get"]["responses"][200]["content"][
        "application/json"
    ]["schema"]
    assert "$ref" in response
    assert "BookOut" in schema["components"]["schemas"]
