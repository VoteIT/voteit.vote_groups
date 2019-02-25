# -*- coding: utf-8 -*-
from arche.models.evolver import BaseEvolver


VERSION = 1


class GroupsEvolver(BaseEvolver):
    name = 'voteit.vote_groups'
    sw_version = VERSION
    initial_db_version = VERSION


def includeme(config):
    config.add_evolver(GroupsEvolver)
