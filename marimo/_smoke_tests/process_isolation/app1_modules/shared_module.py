"""This module is imported by app1.py as 'shared_module'.

Both app1 and app2 import a module named 'shared_module' but from different
directories. Without process isolation, whichever loads first wins.
With process isolation, each app gets its own copy.
"""

APP_NAME = "app1"
MAGIC_NUMBER = 111


def get_identity():
    return {"app": APP_NAME, "magic": MAGIC_NUMBER}
