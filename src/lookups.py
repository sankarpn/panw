def common_name(country: dict) -> str:
    """Canonical common name from a REST Countries country object.

    Shared so cross-reference / consistency tests extract comparable keys the
    same way instead of inlining the parse in each test.
    """
    return country["name"]["common"]


def region_of(country: dict) -> str:
    """Region name from a REST Countries country object (e.g. 'Europe', 'Asia')."""
    return country["region"]
