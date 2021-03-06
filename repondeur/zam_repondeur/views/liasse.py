from pyramid.httpexceptions import HTTPFound
from pyramid.request import Request
from pyramid.response import Response
from pyramid.view import view_config

from zam_repondeur.fetch.an.liasse_xml import import_liasse_xml
from zam_repondeur.models import Lecture
from zam_repondeur.resources import LectureResource
from zam_repondeur.views.lectures import _add_or_update_amendements, _set_flash_messages


@view_config(context=LectureResource, name="import_liasse_xml")
def upload_liasse_xml(context: LectureResource, request: Request) -> Response:
    _do_upload_liasse_xml(context, request)
    return HTTPFound(location=request.resource_url(context))


def _do_upload_liasse_xml(context: LectureResource, request: Request) -> Response:
    try:
        liasse_field = request.POST["liasse"]
    except KeyError:
        request.session.flash(("warning", "Veuillez d’abord sélectionner un fichier"))
        return

    if liasse_field == b"":
        request.session.flash(("warning", "Veuillez d’abord sélectionner un fichier"))
        return

    try:
        amendements = import_liasse_xml(liasse_field.file)
    except ValueError:
        request.session.flash(("danger", "Le format du fichier n’est pas valide."))
        return

    if len(amendements) == 0:
        request.session.flash(
            ("warning", "Aucun amendement n’a été trouvé dans ce fichier.")
        )
        return

    lecture = context.model()
    filtered_amendements = [
        amendement
        for amendement in amendements
        if amendement.chambre == lecture.chambre
        and amendement.session == lecture.session
        and amendement.num_texte == lecture.num_texte
        and amendement.organe == lecture.organe
    ]
    ignored = len(amendements) - len(filtered_amendements)

    if len(filtered_amendements) == 0:
        amendement = amendements[0]
        other_lecture = Lecture(
            chambre=amendement.chambre,
            session=amendement.session,
            num_texte=amendement.num_texte,
            organe=amendement.organe,
        )
        request.session.flash(
            ("danger", f"La liasse correspond à une autre lecture ({other_lecture}).")
        )
        return

    if ignored > 0:
        request.session.flash(
            ("warning", f"{ignored} amendements ignorés car non liés à cette lecture.")
        )

    added, updated, unchanged = _add_or_update_amendements(filtered_amendements)
    assert added + updated + unchanged == len(filtered_amendements)
    _set_flash_messages(request, added, updated, unchanged)
