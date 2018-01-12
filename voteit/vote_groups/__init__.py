# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from pyramid.i18n import TranslationStringFactory

PROJECTNAME = 'voteit.vote_groups'
_ = TranslationStringFactory(PROJECTNAME)


def includeme(config):
    config.include('.views')
    config.include('.models')
    config.include('.schemas')
