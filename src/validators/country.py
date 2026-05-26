from pydantic import BaseModel, ConfigDict


class CountryValidator(BaseModel):
    """Schema for a REST Countries country object — the fields ARE the schema.

    A pydantic model in strict mode: no type coercion, so the response types must
    match exactly (the same guarantee the old isinstance checks gave). Extra
    fields in the response are ignored by default.
    """

    model_config = ConfigDict(strict=True)

    name: dict
    capital: list
    population: int
    currencies: dict
    languages: dict

    @classmethod
    def validate(cls, raw: dict) -> "CountryValidator":
        return cls.model_validate(raw)  # raises pydantic.ValidationError on mismatch
