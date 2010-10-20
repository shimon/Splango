#!/usr/bin/env python

from distutils.core import setup

setup(name='Splango',
      version='0.1',
      description='Split (A/B) testing library for Django',
      author='Shimon Rura',
      author_email='shimon@rura.org',
      url='http://github.com/shimon/Splango',
      packages=['splango','splango.templatetags'],
      )
