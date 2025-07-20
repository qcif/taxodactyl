"""Get country codes from full-name country string."""

import pycountry


def get_code(country_name):
    try:
        country = pycountry.countries.lookup(country_name)
        return country.alpha_2
    except LookupError:
        return None


if __name__ == '__main__':
    country = "China"
    code = get_code(country)
    print(f"{country} -> {code}")
