# -*- coding: utf-8 -*-
"""Navigator Admin Meta information.
   Navigator Admin Dashboard is a simple Admin panel made with Boostrap 5.
"""

__title__ = 'navigator_admin'
__description__ = ('Navigator Admin is a simple Admin panel '
                   'made with Boostrap 5 for aiohttp and navigator.')
__version__ = '0.0.1'  # pragma: no cover
__author__ = 'Jesus Lara'
__author_email__ = 'jesuslarag@gmail.com'
__license__ = 'BSD license'


def get_version() -> tuple: # pragma: no cover
   """
   Get nav-auth version as tuple.
   """
   return tuple(x for x in __version__.split('.')) # pragma: no cover
