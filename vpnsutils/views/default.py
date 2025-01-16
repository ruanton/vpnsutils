from pyramid.view import view_config
from pyramid.request import Request

# module imports
from zmodels import AppRoot

# local imports
from ..settings import settings


@view_config(context=AppRoot, renderer='vpnsutils:templates/mytemplate.jinja2')
def my_view(request: Request):
    _unused = request
    _app_root: AppRoot = request.context
    return {'project': 'vpnsutils', 'xui_name': settings.xui_name}
