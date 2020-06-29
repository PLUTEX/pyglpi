import unittest
import doctest

import pyglpi


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(pyglpi))
    return tests


if __name__ == '__main__':
    unittest.main()
