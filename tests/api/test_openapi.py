from src.main import create_app


def test_no_route_exposes_request_as_a_parameter():
    schema = create_app().openapi()

    offenders = [
        f"{method.upper()} {path}"
        for path, operations in schema["paths"].items()
        for method, op in operations.items()
        for param in op.get("parameters", [])
        if param["name"] == "request"
    ]

    assert not offenders, f"routes leaking `request` as a parameter: {offenders}"
