from collections.abc import Callable
from pathlib import Path
from typing import Union

from aiohttp import hdrs, web, web_exceptions
from navigator.extensions import BaseExtension
from navigator.responses import Response
from navigator_auth.decorators import allowed_groups
from navigator_auth.exceptions import UserNotFound
from navigator_session import get_session


class AdminPanel(BaseExtension):
    name: str = 'auth'
    app: web.Application = None
    routes: list = []

    def __init__(
            self,
            app_name: str = None,
            uri_prefix: str = '/admin',
            title: str = 'Navigator Admin',
            template_path: Union[str, Path] = None,
            **kwargs
        ) -> None:
        self.uri_prefix = uri_prefix
        self.title = title
        if isinstance(template_path, str):
            self.template_path = Path(template_path).resolve()
        super(AdminPanel, self).__init__(
            app_name=app_name,
            **kwargs
        )

    def add_model(self, cls: Callable, route_name: str):
        router = self.app.router
        rt = fr"{self.uri_prefix}/{route_name}{{meta:\:?(.*)}}"
        router.add_view(
            rt,
            cls,
            name=f"admin_{cls.name}"
        )
        r = {
            "name": route_name.lower(),
            "title": route_name,
            "icon": cls.icon,
            "path": f"{self.uri_prefix}/{route_name}"
        }
        cls.uri_prefix = self.uri_prefix
        self.routes.append(r)



    def setup(self, app: web.Application):
        """setup.
        Configure Admin Panel routes for Navigator.
        """
        super(AdminPanel, self).setup(app)

        ### adding routes:
        router = self.app.router
        # ## admin index
        router.add_route(
            "GET",
            f"{self.uri_prefix}",
            self.admin_index,
            name="admin_index"
        )
        ## Login
        router.add_route(
            "*",
            f"{self.uri_prefix}/login",
            self.admin_login,
            name="admin_login"
        )
        # Logout:
        router.add_route(
            "get",
            f"{self.uri_prefix}/logout",
            self.admin_logout,
            name="admin_logout"
        )
        ### added declared admin handlers

    async def admin_logout(self, request: web.Request) -> web.StreamResponse:
        auth = request.app["auth"]
        location = request.app.router['admin_login'].url_for()
        try:
            response = web.HTTPFound(location=location)
            await auth.session.storage.forgot(request, response)
            raise response
        except KeyError as ex:
            raise web.HTTPBadRequest(
                reason=f"Error on Logout: {ex}",
                headers={
                    hdrs.CONTENT_TYPE: 'text/html',
                    hdrs.CONNECTION: 'keep-alive',
                }
            ) from ex

    async def admin_login(self, request: web.Request) -> web.StreamResponse:
        if request.method == "GET":
            view = request.app['template'].view
            args = {
                "page_url": "localhost",
                "title": self.title,
                "main_url": self.uri_prefix,
                "auth_method": 'BasicAuth'
            }
            return await view('login.html', args)
        elif request.method == 'POST':
            auth_method = request.headers.get('x-auth-method', 'BasicAuth')
            auth = request.app["auth"]
            try:
                backend = auth.backends[auth_method]
                if userdata := await backend.authenticate(request):
                    location = request.app.router['admin_index'].url_for()
                    token = userdata['token']
                    headers = {
                        "Authorization": f"Bearer {token}"
                    }
                    response = web.HTTPFound(location=location, headers=headers)
                    await auth.session.storage.load_session(request, userdata, response=response)
                    raise response
                else:
                    raise web.HTTPUnauthorized(
                        reason="Unauthorized: Access Denied to this resource.",
                        headers={
                            hdrs.CONTENT_TYPE: 'text/html',
                            hdrs.CONNECTION: 'keep-alive',
                        }
                    )
            except UserNotFound as err:
                raise web.HTTPForbidden(
                    reason=f"{err.message}"
                )
            except KeyError as ex:
                raise web.HTTPBadRequest(
                    reason="API Key Backend Auth is not enabled.",
                    headers={
                        hdrs.CONTENT_TYPE: 'text/html',
                        hdrs.CONNECTION: 'keep-alive',
                    }
                ) from ex
        else:
            raise web_exceptions.HTTPMethodNotAllowed()

    async def admin_index(self, request: web.Request) -> web.StreamResponse:
        location = request.app.router['admin_login'].url_for()
        if request.get('authenticated', False) is False:
            raise web.HTTPFound(location=location)
        session = await get_session(request)
        if not session: # also there is no session:
            raise web.HTTPFound(location=location)
        view = request.app['template'].view
        args = {
            "page_url": "localhost",
            "title": self.title,
            "main_url": self.uri_prefix,
            "logout_url": f"{self.uri_prefix}/logout",
            "admin_routes": self.routes
        }
        return await view('index.html', args)
