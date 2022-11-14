from navigator_auth.models import Client, Organization, Program, Group, Permission
from navigator_admin import AdminHandler


class ClientHandler(AdminHandler):
    model = Client
    icon: str = 'codesandbox'
    name: str = 'Client'
    pk: list = ['client_id']


class OrgHandler(AdminHandler):
    model = Organization
    name: str = 'Organization'
    icon: str = 'globe'
    pk: list = ['org_id']

class ProgramHandler(AdminHandler):
    model = Program
    name: str = 'Program'
    icon: str = 'grid'
    pk: list = ['program_id']

class GroupHandler(AdminHandler):
    model = Group
    name: str = 'Group'
    icon: str = 'users'
    pk: list = ['group_id']

class PermissionHandler(AdminHandler):
    model = Permission
    name: str = 'Permission'
    icon: str = 'layers'
    pk: list = ['permission_id']
