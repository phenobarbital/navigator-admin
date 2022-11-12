"""
  Navigator Admin.

  Basic Dashboard Admin Panel for Navigator.
"""
from .version import __author__, __description__, __title__, __version__, get_version

from .admin import AdminHandler


__all__ = ('AdminHandler', )
