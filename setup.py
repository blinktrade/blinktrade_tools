#!/usr/bin/env python

from setuptools import setup

version = "0.1"

REQUIREMENTS = [i.strip() for i in open("requirements.txt").readlines()]

setup(
  name="blinktrade_tools",
  version=version,
  packages = [
    "blinktrade_tools",
  ],
  author="Rodrigo Souza",
  entry_points = { 'console_scripts':
     [
       'blinktrade_exporter = blinktrade_tools.exporter:main'
     ]
  },

  install_requires=REQUIREMENTS,
  author_email='r@blinktrade.com',
  url='https://github.com/blinktrade/blinktrade_tools',
  license='http://www.gnu.org/copyleft/gpl.html',
  description='Blinktrade tools'
)