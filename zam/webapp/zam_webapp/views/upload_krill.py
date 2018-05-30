import os
import re
from tempfile import TemporaryDirectory
from typing import Iterator, List, Tuple

from pyramid.httpexceptions import HTTPFound
from pyramid.request import Request
from pyramid.response import Response
from pyramid.view import view_config
from xlrd import open_workbook, XL_CELL_NUMBER
from xlrd.sheet import Cell

from zam_aspirateur.amendements.models import Amendement
from zam_aspirateur.amendements.writer import write_json_for_viewer

from zam_visionneuse.loaders import load_aspirateur_source
from zam_visionneuse.models import load_data
from zam_visionneuse.templates import render_and_save_html

from zam_webapp.utils import environ
from zam_webapp.views.lectures import Lecture


@view_config(route_name="upload_krill", request_method="POST")
def upload_krill(request: Request) -> Response:

    next_url = request.route_url(
        "lecture",
        chambre=request.matchdict["chambre"],
        session=request.matchdict["session"],
        num_texte=request.matchdict["num_texte"],
    )

    lecture = Lecture(  # type: ignore
        chambre=request.matchdict["chambre"],
        session=request.matchdict["session"],
        num_texte=request.matchdict["num_texte"],
    )

    # filename = request.POST['xls_file'].filename
    # log filename?

    xls_file = request.POST["xls_file"].file
    xls_file.seek(0)
    xls_data = xls_file.read()

    try:
        amendements = read_excel_data(xls_data)
    except BadFormat:
        request.session.flash(("alert", "Le fichier n'est pas dans le format attendu."))
        return HTTPFound(location=next_url)

    with TemporaryDirectory() as tmp_dir:
        filename = os.path.join(tmp_dir, "visionneuse.json")

        write_json_for_viewer(
            id_projet=0, title=str(lecture), amendements=amendements, filename=filename
        )

        visionneuse_env = {
            "ZAM_ASPIRATEUR_SOURCE": filename,
            "ZAM_JAUNES_SOURCE": tmp_dir,
        }
        with environ(visionneuse_env):
            _, aspirateur_items = load_aspirateur_source()
            articles, amendements, reponses = load_data([], aspirateur_items)
            html = render_and_save_html("Titre", articles, amendements, reponses)
            response = Response(html)
            return response

    # request.session.flash(("success", "Fichier importé avec succès."))
    # return HTTPFound(location=next_url)


class BadFormat(Exception):
    pass


EXPECTED_HEADER = [
    "",
    "Art. de la loi",
    "N° Amdt.",
    "Bureau",
    "Amendement gouvernemental",
    "Alarme",
    "Sans réponse",
    "Sans validation",
    "Amdt. père",
    "Sous amdt.",
    "Rectif.",
    "Auteur(s)",
    "Objet",
    "Bureau 2",
    "Bureau 3",
    "Position du GOUVERNEMENT",
    "Validation",
    "Dossier Ministre",
    "Vigilance",
    "Observations",
    "Observation (réponse)",
]


def read_excel_data(xls_data: bytes) -> Iterator[Amendement]:
    workbook = open_workbook(file_contents=xls_data)
    sheet = workbook.sheet_by_index(0)
    row_gen = sheet.get_rows()
    header = [cell.value for cell in next(row_gen)]
    if header != EXPECTED_HEADER:
        raise BadFormat
    for row in row_gen:
        yield parse_row(row)


def parse_row(row: List[Cell]) -> Amendement:
    type_, num, mult, pos = parse_article(cell_text(row[1]))
    return Amendement(
        subdiv_type=type_,
        subdiv_num=num,
        subdiv_mult=mult,
        subdiv_pos=pos,
        num=str(int(row[2].value)),
        rectif=int(row[10].value) if is_number(row[10]) else 0,
        auteur=row[11].value,
        objet=row[12].value,
        avis=row[15].value,
        observations=row[19].value,
        reponse=row[20].value,
    )


def cell_text(cell: Cell) -> str:
    return str(int(cell.value)) if is_number(cell) else cell.value


def is_number(cell: Cell) -> bool:
    res = cell.ctype == XL_CELL_NUMBER  # type: bool
    return res


ARTICLE_RE = re.compile(
    r"""^
        .*?                                # junk
        (?:(?P<position>avant|après)\s+)?  # avant, après
        (?P<num>PREMIER|\d+)               # numéro de l'article
        (?:\s(?P<mult>\w+))?               # bis, ter...
    $""",
    re.VERBOSE,
)


def parse_article(libelle: str) -> Tuple[int, str, str]:
    libelle = libelle.strip()
    mo = ARTICLE_RE.match(libelle)
    if mo is not None:
        num = mo.group("num")
        mult = mo.group("mult") or ""
        position = mo.group("position") or ""
        return 1 if num == "PREMIER" else int(num), mult, position
    raise ValueError(f"Could not parse article number {libelle!r}")
