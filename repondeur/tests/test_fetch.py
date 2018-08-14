from pathlib import Path
import transaction

import pytest
import responses


class TestGetPossibleUrls:
    def test_assemblee_nationale(self):
        from zam_repondeur.fetch import get_possible_texte_urls
        from zam_repondeur.models import Lecture

        lecture = Lecture(
            chambre="an",
            session="15",
            num_texte=269,
            titre="Titre lecture",
            organe="PO420120",
        )
        assert get_possible_texte_urls(lecture) == [
            "http://www.assemblee-nationale.fr/15/projets/pl0269.asp",
            "http://www.assemblee-nationale.fr/15/ta-commission/r0269-a0.asp",
        ]

    def test_senat(self):
        from zam_repondeur.fetch import get_possible_texte_urls
        from zam_repondeur.models import Lecture

        lecture = Lecture(
            chambre="senat",
            session="2017-2018",
            num_texte=63,
            titre="Titre lecture",
            organe="PO78718",
        )
        assert get_possible_texte_urls(lecture) == [
            "https://www.senat.fr/leg/pjl17-063.html"
        ]


@responses.activate
def test_get_articles_an(app, lecture_an, amendements_an):
    from zam_repondeur.fetch import get_articles
    from zam_repondeur.models import DBSession, Amendement

    responses.add(
        responses.GET,
        "http://www.assemblee-nationale.fr/15/projets/pl0269.asp",
        body=(Path(__file__).parent / "sample_data" / "pl0269.html").read_text(
            "utf-8", "ignore"
        ),
        status=200,
    )

    get_articles(lecture_an)

    amendement = DBSession.query(Amendement).filter(Amendement.num == 666).first()
    assert amendement.article.contenu["001"].startswith("Au titre de l'exercice 2016")


@responses.activate
def test_get_articles_an_seance(app, lecture_an, amendements_an):
    from zam_repondeur.fetch import get_articles
    from zam_repondeur.models import DBSession, Amendement

    with transaction.manager:
        lecture_an.num_texte = 575
        lecture_an.organe = "PO717460"
        lecture_an.titre = "Première lecture – Séance publique"

        amendements_an[0].article.num = "2"

        # The objects are no longer bound to a session here, as they were created in a
        # previous transaction, so we add them to the current session to make sure that
        # our changes will be committed with the current transaction
        DBSession.add(lecture_an)
        DBSession.add_all(amendements_an)

    responses.add(
        responses.GET,
        "http://www.assemblee-nationale.fr/15/projets/pl0575.asp",
        status=404,
    )
    responses.add(
        responses.GET,
        "http://www.assemblee-nationale.fr/15/ta-commission/r0575-a0.asp",
        body=(Path(__file__).parent / "sample_data" / "r0575-a0.html").read_text(
            "utf-8", "ignore"
        ),
        status=200,
    )

    get_articles(lecture_an)

    amendement = DBSession.query(Amendement).filter(Amendement.num == 666).first()
    assert amendement.article.contenu["001"].startswith("Le code des relations entre")


@responses.activate
def test_get_articles_senat(app, lecture_senat, amendements_senat):
    from zam_repondeur.fetch import get_articles
    from zam_repondeur.models import DBSession, Amendement

    responses.add(
        responses.GET,
        "https://www.senat.fr/leg/pjl17-063.html",
        body=(Path(__file__).parent / "sample_data" / "pjl17-063.html").read_text(
            "utf-8", "ignore"
        ),
        status=200,
    )

    get_articles(lecture_senat)

    amendement = DBSession.query(Amendement).filter(Amendement.num == 6666).first()
    assert amendement.article.contenu["001"].startswith("Au titre de l'exercice 2016")


@responses.activate
def test_get_articles_senat_with_mult(app, lecture_senat, amendements_senat):
    from zam_repondeur.fetch import get_articles
    from zam_repondeur.models import DBSession, Amendement

    responses.add(
        responses.GET,
        "https://www.senat.fr/leg/pjl17-063.html",
        body=(Path(__file__).parent / "sample_data" / "pjl17-063.html").read_text(
            "utf-8", "ignore"
        ),
        status=200,
    )

    with transaction.manager:
        amendement = amendements_senat[0]
        amendement.article.num = "4"
        amendement.article.mult = "bis"

        # The objects are no longer bound to a session here, as they were created in a
        # previous transaction, so we add them to the current session to make sure that
        # our changes will be committed with the current transaction
        DBSession.add(amendement)

    get_articles(lecture_senat)

    amendement = DBSession.query(Amendement).filter(Amendement.num == 6666).first()
    assert amendement.article.contenu["001"].startswith("Ne donnent pas lieu à")


def test_get_section_title():
    from zam_repondeur.fetch import get_section_title

    items = [
        {
            "id": "P1",
            "titre": "Dispositions relatives à l'exercice 2016",
            "type": "section",
            "type_section": "partie",
        },
        {
            "alineas": {},
            "order": 1,
            "section": "P1",
            "statut": "none",
            "titre": "1er",
            "type": "article",
        },
    ]
    article = {
        "alineas": {},
        "order": 1,
        "section": "P1",
        "statut": "none",
        "titre": "1er",
        "type": "article",
    }
    title = get_section_title(items, article)
    assert title == "Dispositions relatives à l'exercice 2016"


def test_get_section_title_unknown_reference():
    from zam_repondeur.fetch import get_section_title

    items = [
        {
            "id": "P1",
            "titre": "Dispositions relatives à l'exercice 2016",
            "type": "section",
            "type_section": "partie",
        },
        {
            "alineas": {},
            "order": 1,
            "section": "P1",
            "statut": "none",
            "titre": "1er",
            "type": "article",
        },
    ]
    article = {
        "alineas": {},
        "order": 1,
        "section": "FOO",
        "statut": "none",
        "titre": "1er",
        "type": "article",
    }
    assert get_section_title(items, article) == ""


@pytest.mark.parametrize(
    "input,num,mult",
    [
        ("2", "2", ""),
        ("1er", "1", ""),
        ("3 bis", "3", "bis"),
        ("5 ter AAA", "5", "ter AAA"),
    ],
)
def test_get_article_num_mult(input, num, mult):
    from zam_repondeur.fetch import get_article_num_mult

    assert get_article_num_mult({"titre": input}) == (num, mult)
