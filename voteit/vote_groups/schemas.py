# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import colander
import deform
from arche.schemas import userid_hinder_widget
from arche.validators import existing_userids
from pyramid.decorator import reify
from pyramid.httpexceptions import HTTPNotFound

from voteit.vote_groups import _
from voteit.vote_groups.interfaces import IMeetingVoteGroups


class PrimariesMembersSequence(colander.SequenceSchema):
    primaries = colander.SchemaNode(colander.String(),
                                    title=_("Vote group primaries"),
                                    description=_("Start typing a userid"),
                                    widget=userid_hinder_widget,
                                    validator=existing_userids)


class StandinMembersSequence(colander.SequenceSchema):
    standins = colander.SchemaNode(colander.String(),
                                   title=_("Vote group stand-ins"),
                                   description=_("Start typing a userid"),
                                   widget=userid_hinder_widget,
                                   validator=existing_userids)


@colander.deferred
class VoteGroupValidator(object):
    def __init__(self, node, kw):
        self.request = kw['request']

    @reify
    def groups(self):
        return IMeetingVoteGroups(self.request.meeting)

    @reify
    def group(self):
        try:
            group_id = self.request.GET['vote_group']
        except KeyError:
            raise HTTPNotFound
        return self.groups[group_id]

    def __call__(self, form, value):
        exc = colander.Invalid(form, 'Error when selecting group members')
        primaries = set(value['primaries'])
        standins = set(value['standins'])
        if primaries.intersection(standins):
            exc['standins'] = _('Same person can not be both primary and stand-in.')
        # TODO Check other vote groups for membership
        for grp in self.groups.values():
            if grp == self.group:
                continue
            grp_members = set(grp.primaries).union(grp.standins)
            intersect = primaries.intersection(grp_members)
            if intersect:
                exc['primaries'] = _('User(s) ${users} has membership in other group.',
                                     mapping={'users': ', '.join(intersect)})
            intersect = standins.intersection(grp_members)
            if intersect:
                exc['standins'] = _('User(s) ${users} has membership in other group.',
                                    mapping={'users': ', '.join(intersect)})

        for user_id in self.group.assignments.keys():
            if user_id not in primaries:
                exc['primaries'] = _('Cannot remove users with transferred voter permission.')
        for user_id in self.group.assignments.values():
            if user_id not in standins:
                exc['standins'] = _('Cannot remove users with transferred voter permission.')

        if len(exc.children):
            raise exc


class EditMeetingVoteGroupSchema(colander.Schema):
    title = colander.SchemaNode(colander.String(),
                                title=_("Title"))
    description = colander.SchemaNode(colander.String(),
                                      title=_("Description"),
                                      missing="",
                                      widget=deform.widget.TextAreaWidget())
    primaries = PrimariesMembersSequence(title=_("Vote group primaries"),
                                         description=_("Add one UserID per row."))
    standins = StandinMembersSequence(title=_("Vote group stand-ins"),
                                         description=_("Add one UserID per row."))
    validator = VoteGroupValidator


@colander.deferred
def deferred_choices_widget(node, kw):
    choices = kw.get('choices')
    return deform.widget.SelectWidget(values=choices)


class AssignVoteSchema(colander.Schema):
    standin = colander.SchemaNode(
        colander.String(),
        widget=deferred_choices_widget,
    )


def includeme(config):
    config.add_content_schema('MeetingVoteGroup', EditMeetingVoteGroupSchema, 'edit')
