# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from pyramid.i18n import TranslationStringFactory


_ = TranslationStringFactory('voteit.vote_groups')


def includeme(config):
    config.include('.views')
    config.include('.models')
    config.include('.schemas')
    config.add_translation_dirs('voteit.vote_groups:locale/')
