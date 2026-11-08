"""City display names used in index.json."""

from dataclasses import dataclass


@dataclass(frozen=True)
class City:
    id: str
    name_en: str
    name_gu: str


CITIES: dict[str, City] = {
    c.id: c
    for c in [
        City("surat", "Surat", "સુરત"),
        City("ahmedabad", "Ahmedabad", "અમદાવાદ"),
        City("vadodara", "Vadodara", "વડોદરા"),
        City("rajkot", "Rajkot", "રાજકોટ"),
        City("gandhinagar", "Gandhinagar", "ગાંધીનગર"),
        City("bhavnagar", "Bhavnagar", "ભાવનગર"),
        City("jamnagar", "Jamnagar", "જામનગર"),
        City("junagadh", "Junagadh", "જૂનાગઢ"),
    ]
}


def get_city(city_id: str) -> City:
    try:
        return CITIES[city_id]
    except KeyError:
        # Unknown city ids still work; the title-cased id is used as the English name.
        name = city_id.replace("-", " ").title()
        return City(city_id, name, name)
