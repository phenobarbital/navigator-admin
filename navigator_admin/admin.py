from pathlib import Path
from typing import Union
import orjson
from aiohttp import web, hdrs, web_exceptions
from navigator.extensions import BaseExtension
from navigator.responses import Response
from navigator_auth.decorators import allowed_groups


class AdminHandler(BaseExtension):
    name: str = 'auth'
    app: web.Application = None

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
        super(AdminHandler, self).__init__(
            app_name=app_name,
            **kwargs
        )

    def setup(self, app: web.Application):
        """setup.
        Configure Admin Panel routes for Navigator.
        """
        super(AdminHandler, self).setup(app)

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
        # router.add_route(
        #     "GET",
        #     f"/{self.uri_prefix}/logout",
        #     self.admin_logout,
        #     name="admin_logout"
        # )

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
                    raise web.HTTPFound(location=location, headers=headers)
                else:
                    raise web.HTTPUnauthorized(
                        reason="Unauthorized: Access Denied to this resource.",
                        headers={
                            hdrs.CONTENT_TYPE: 'text/html',
                            hdrs.CONNECTION: 'keep-alive',
                        }
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
        view = request.app['template'].view
        args = {
            "page_url": "localhost",
            "title": self.title,
            "main_url": self.uri_prefix,
            "logout_url": f"{self.uri_prefix}/logout"
        }
        return await view('index.html', args)
