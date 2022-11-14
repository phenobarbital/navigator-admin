"""
Model Handler: Abstract Model for managing Model with Views.
"""
from typing import Union
from inflector import Inflector
from aiohttp import web
from datamodel import BaseModel
from datamodel.exceptions import ValidationError
from asyncdb.exceptions import (
    DriverError,
    ProviderError,
    NoDataFound,
    StatementError
)
from navigator.views import BaseView
from navigator_session import get_session, SessionData
from navigator_auth.exceptions import AuthException
from navigator_auth.conf import AUTH_SESSION_OBJECT


class AdminHandler(BaseView):
    model: BaseModel = None
    name: str = 'Model'
    pk: Union[str, list] = 'id'
    _columns: list = []
    uri_prefix: str = '/admin'

    icon: str = 'book'

    allowed_groups: list = ['superuser']

    can_create: bool = True
    can_delete: bool = True
    can_update: bool = True

    def __init__(self, request: web.Request, *args, **kwargs) -> None:
        super(AdminHandler, self).__init__(request, *args, **kwargs)
        self.__name__ = type(self).__name__
        if not self._columns:
            # calculated based on Model
            for name in self.model.__columns__:
                self._columns.append(name)
        print(f'LOADED ADMIN MODEL FOR {self.__name__}')
        self.inflector = Inflector()

    @property
    async def name(self):
        return self.__name__

    async def session(self):
        session = None
        try:
            session = await get_session(self.request)
            member = False
            try:
                userinfo = session[AUTH_SESSION_OBJECT]
            except (TypeError, KeyError):
                member = False
                userinfo = {}
            if 'groups' in userinfo:
                member = bool(not set(userinfo['groups']).isdisjoint(self.allowed_groups))
            elif session:
                user = session.decode('user')
                if user:
                    for group in user.groups:
                        if group.group in self.allowed_groups:
                            member = True
            if member is False:
                raise web.HTTPUnauthorized(
                    reason="Access Denied"
                )
        except web.HTTPUnauthorized:
            raise
        except (ValueError, RuntimeError) as err:
            return self.critical(
                reason="Error Decoding Session",
                request=self.request,
                exception=err
            )
        return session

    async def head(self):
        """ Getting Client information."""
        session = await self.session()
        if not session:
            return self.error(
                reason="Unauthorized",
                status=403
            )
        ## calculating resource:
        response = self.model.schema(as_dict=True)
        columns = list(response["properties"].keys())
        size = len(str(response))
        headers = {
            "Content-Length": size,
            "X-Columns": f"{columns!r}",
            "X-Model": self.model.__name__,
            "X-Tablename": self.model.Meta.name,
            "X-Schema": self.model.Meta.schema,
        }
        return self.no_content(
            headers=headers
        )

    async def validate(self) -> SessionData:
        try:
            session = await self.session()
            if not session:
                raise self.error(
                    reason="Unauthorized",
                    status=403
                )
            return session
        except web.HTTPUnauthorized:
            raise
        except (ValueError, RuntimeError) as ex:
            raise self.error(
                reason=f"Unauthorized: {ex}",
                status=403
            ) from ex

    async def get(self):
        """ Getting Model information."""
        # TODO: filter capabilities
        session = await self.validate()
        ## getting all clients:
        params = self.match_parameters(self.request)
        try:
            if params['meta'] == ':meta':
                # returning JSON schema of Model:
                response = self.model.schema(as_dict=True)
                return self.json_response(response)
        except KeyError:
            pass
        try:
            data = await self.json_data()
        except (TypeError, ValueError, AuthException):
            data = None
        ## if param is None, rendering the template:
        print('PARAMS  IS ', params)
        if params['meta'] == '':
            view = self.request.app['template'].view
            title = self.inflector.pluralize(word=self.name)
            args = {
                "page_url": "localhost",
                "title": title,
                "main_url": self.uri_prefix,
                "logout_url": f"{self.uri_prefix}/logout",
                "admin_routes": []
            }
            return await view('model.html', args)
        else:
            ## validate directly with model:
            db = self.request.app['database']
            ## getting first the id from params or data:
            args = {}
            if isinstance(self.pk, str):
                try:
                    objid = data[self.pk]
                except (TypeError, KeyError):
                    try:
                        objid = params['id']
                    except KeyError:
                        objid = None
                if objid:
                    args = {
                        self.pk: objid
                    }
            elif isinstance(self.pk, list):
                try:
                    paramlist = params['id'].split('/')
                    if len(paramlist) != len(self.pk):
                        return self.error(
                            reason=f"Invalid Number of URL elements for PK: {self.pk}, {paramlist!r}",
                            status=410
                        )
                    args = {}
                    for key in self.pk:
                        args[key] = paramlist.pop(0)
                except KeyError:
                    pass
            else:
                return self.error(
                    reason=f"Invalid PK definition for {self.name}: {self.pk}",
                    status=410
                )
            if args:
                # get data for specific client:
                async with await db.acquire() as conn:
                    self.model.Meta.connection = conn
                    # look for this client, after, save changes
                    error = {
                        "error": f"{self.name} was not Found"
                    }
                    try:
                        result = await self.model.get(**args)
                    except NoDataFound:
                        self.error(
                            exception=error,
                            status=403
                        )
                    if not result:
                        self.error(
                            exception=error,
                            status=403
                        )
                    return self.json_response(result)
            else:
                # TODO: add FILTER method
                try:
                    async with await db.acquire() as conn:
                        self.model.Meta.connection = conn
                        result = await self.model.all()
                        return self.json_response(result)
                except ValidationError as ex:
                    error = {
                        "error": f"Unable to load {self.name} info from Database",
                        "payload": ex.payload,
                    }
                    return self.critical(
                        reason=error,
                        status=501
                    )
                except TypeError as ex:
                    error = {
                        "error": f"Invalid payload for {self.name}",
                        "payload": str(ex),
                    }
                    return self.error(
                        exception=error,
                        status=406
                    )
                except (DriverError, ProviderError, RuntimeError):
                    error = {
                        "error": "Database Error",
                        "payload": str(ex),
                    }
                    return self.critical(
                        reason=error,
                        status=500
                    )

    async def put(self):
        """ Creating Model information."""
        session = await self.validate()
        if self.can_create is False:
            raise self.error(
                reason="INSERT options are not allowed.",
                status=405
            )
        try:
            data = await self.json_data()
        except (TypeError, ValueError, AuthException):
            return self.error(
                reason=f"Invalid {self.name} Data",
                status=403
            )
        ## validate directly with model:
        try:
            resultset = self.model(**data) # pylint: disable=E1102
            db = self.request.app['authdb']
            async with await db.acquire() as conn:
                resultset.Meta.connection = conn
                result = await resultset.insert()
                return self.json_response(result, status=201)
        except ValidationError as ex:
            error = {
                "error": f"Unable to insert {self.name} info",
                "payload": ex.payload,
            }
            return self.error(
                reason=error,
                status=406
            )
        except StatementError as ex:
            # UniqueViolation, already exists:
            error = {
                "error": f"Record already exists for {self.name}",
                "payload": str(ex),
            }
            return self.error(
                exception=error,
                status=412
            )
        except (TypeError, AttributeError, ValueError) as ex:
            error = {
                "error": f"Invalid payload for {self.name}",
                "payload": str(ex),
            }
            return self.error(
                exception=error,
                status=406
            )

    async def patch(self):
        """ Patch an existing Client or retrieve the column names."""
        session = await self.validate()
        if self.can_update is False:
            raise self.error(
                reason="UPDATE options are not allowed.",
                status=405
            )
        ### get session Data:
        params = self.match_parameters()
        try:
            if params['meta'] == ':meta':
                ## returning the columns on Model:
                fields = self.model.__fields__
                return self.json_response(fields)
        except KeyError:
            pass
        try:
            data = await self.json_data()
        except (TypeError, ValueError, AuthException):
            return self.error(
                reason=f"Invalid {self.name} Data",
                status=403
            )
        ## validate directly with model:
        ## getting first the id from params or data:
        args = {}
        if isinstance(self.pk, str):
            try:
                objid = data[self.pk]
            except (TypeError, KeyError):
                objid = params['id']
            args = {
                self.pk: objid
            }
        elif isinstance(self.pk, list):
            try:
                paramlist = params['id'].split('/')
                if len(paramlist) != len(self.pk):
                    return self.error(
                        reason=f"Invalid Number of URL elements for PK: {self.pk}, {paramlist!r}",
                        status=410
                    )
                args = {}
                for key in self.pk:
                    args[key] = paramlist.pop(0)
            except KeyError:
                pass
        else:
            return self.error(
                reason=f"Invalid PK definition for {self.name}: {self.pk}",
                status=410
            )
        db = self.request.app['authdb']
        if args:
            ## getting client
            async with await db.acquire() as conn:
                self.model.Meta.connection = conn
                try:
                    result = await self.model.get(**args)
                except NoDataFound:
                    headers = {
                        "x-error": f"{self.name} was not Found"
                    }
                    self.no_content(
                        headers=headers
                    )
                if not result:
                    headers = {
                        "x-error": f"{self.name} was not Found"
                    }
                    self.no_content(
                        headers=headers
                    )
                ## saved with new changes:
                for key, val in data.items():
                    if key in result.get_fields():
                        result.set(key, val)
                data = await result.update()
                return self.json_response(data, status=202)
        else:
            self.error(
                reason=f"Invalid {self.name} Data to Patch",
                status=403
            )

    async def post(self):
        """ Create or Update a Client."""
        session = await self.validate()
        if self.can_update is False or self.can_create is False:
            raise self.error(
                reason="UPDATE/INSERT options are not allowed.",
                status=405
            )
        ### get session Data:
        params = self.match_parameters()
        try:
            data = await self.json_data()
        except (TypeError, ValueError, AuthException):
            return self.error(
                reason=f"Invalid {self.name} Data",
                status=403
            )
        ## validate directly with model:
        ## getting first the id from params or data:
        args = {}
        if isinstance(self.pk, str):
            try:
                objid = data[self.pk]
            except (TypeError, KeyError):
                objid = params['id']
            args = {
                self.pk: objid
            }
        elif isinstance(self.pk, list):
            try:
                paramlist = params['id'].split('/')
                if len(paramlist) != len(self.pk):
                    return self.error(
                        reason=f"Invalid Number of URL elements for PK: {self.pk}, {paramlist!r}",
                        status=410
                    )
                args = {}
                for key in self.pk:
                    args[key] = paramlist.pop(0)
            except KeyError:
                pass
        else:
            return self.error(
                reason=f"Invalid PK definition for {self.name}: {self.pk}",
                status=410
            )
        db = self.request.app['authdb']
        if args:
            async with await db.acquire() as conn:
                self.model.Meta.connection = conn
                # look for this client, after, save changes
                error = {
                    "error": f"{self.name} was not Found"
                }
                try:
                    result = await self.model.get(**args)
                except NoDataFound:
                    # create new Record
                    result = None
                if not result:
                    try:
                        resultset = self.model(**data) # pylint: disable=E1102
                        result = await resultset.insert()
                        return self.json_response(result, status=201)
                    except ValidationError as ex:
                        error = {
                            "error": f"Unable to insert {self.name} info",
                            "payload": ex.payload,
                        }
                        return self.error(
                            reason=error,
                            status=406
                        )
                ## saved with new changes:
                for key, val in data.items():
                    if key in result.get_fields():
                        result.set(key, val)
                data = await result.update()
                return self.json_response(data, status=202)
        else:
            # create a new client based on data:
            try:
                resultset = self.model(**data) # pylint: disable=E1102
                async with await db.acquire() as conn:
                    resultset.Meta.connection = conn
                    result = await resultset.insert() # TODO: migrate to use save()
                    return self.json_response(result, status=201)
            except ValidationError as ex:
                error = {
                    "error": f"Unable to insert {self.name} info",
                    "payload": ex.payload,
                }
                return self.error(
                    reason=error,
                    status=406
                )
            except (TypeError, AttributeError, ValueError) as ex:
                error = {
                    "error": f"Invalid payload for {self.name}",
                    "payload": str(ex),
                }
                return self.error(
                    exception=error,
                    status=406
                )

    async def delete(self):
        """ Delete a Client."""
        session = await self.validate()
        if self.can_delete is False:
            raise self.error(
                reason="DELETE options are not allowed.",
                status=405
            )
        ### get session Data:
        params = self.match_parameters()
        try:
            data = await self.json_data()
        except AuthException:
            data = None
        except (TypeError, ValueError):
            self.error(
                reason=f"Invalid {self.name} Data",
                status=403
            )
        ## getting first the id from params or data:
        args = {}
        if isinstance(self.pk, str):
            try:
                objid = data[self.pk]
            except (TypeError, KeyError):
                objid = params['id']
            args = {
                self.pk: objid
            }
        elif isinstance(self.pk, list):
            try:
                paramlist = params['id'].split('/')
                if len(paramlist) != len(self.pk):
                    return self.error(
                        reason=f"Invalid Number of URL elements for PK: {self.pk}, {paramlist!r}",
                        status=410
                    )
                args = {}
                for key in self.pk:
                    args[key] = paramlist.pop(0)
            except KeyError:
                pass
        else:
            return self.error(
                reason=f"Invalid PK definition for {self.name}: {self.pk}",
                status=410
            )
        db = self.request.app['authdb']
        if args:
            async with await db.acquire() as conn:
                self.model.Meta.connection = conn
                # look for this client, after, save changes
                result = await self.model.get(**args)
                if not result:
                    self.error(
                        reason=f"{self.name} was Not Found",
                        status=204
                    )
                # Delete them this Client
                data = await result.delete()
                return self.json_response(data, status=202)
        else:
            self.error(
                reason=f"Cannot Delete an Empty {self.name}",
                status=204
            )
