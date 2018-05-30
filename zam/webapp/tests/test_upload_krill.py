import pytest

from zam_webapp.views.upload_krill import parse_article


@pytest.mark.parametrize(
    "libelle,article,mult,position",
    [
        ("PREMIER", 1, "", ""),
        ("  PREMIER ", 1, "", ""),
        ("après PREMIER", 1, "", "après"),
        ("1", 1, "", ""),
        ("2", 2, "", ""),
        ("avant 2", 2, "", "avant"),
        ("8 bis", 8, "bis", ""),
        ("8 quater", 8, "quater", ""),
        ("après 8", 8, "", "après"),
        ("après 18", 18, "", "après"),
        ("après 15 bis", 15, "bis", "après"),
        ("Division(s) additionnel(s) après  44", 44, "", "après"),
    ],
)
def test_parse_article(libelle, article, mult, position):
    assert parse_article(libelle) == (article, mult, position)
