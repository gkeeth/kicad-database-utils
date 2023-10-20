#!/usr/bin/env python

import unittest


def main():
    testsuite = unittest.defaultTestLoader.discover(".")
    unittest.TextTestRunner().run(testsuite)


if __name__ == "__main__":
    main()
