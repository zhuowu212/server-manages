import sqlite3
import sys


def test_supported_runtime():
    assert sys.version_info[:2] == (3, 12)
    assert sqlite3.sqlite_version_info >= (3, 51, 3)
