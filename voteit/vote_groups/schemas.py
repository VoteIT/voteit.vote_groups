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


ROLE_CHOICES = (
    ('primary', _('Primary')),
    ('standin', _('Stand-in')),
    ('observer', _('Observer')),
)


class MemberSchema(colander.Schema):
    user = colander.SchemaNode(
        colander.String(),
        title=_("Vote group member"),
        description=_("Start typing a userid"),
        widget=userid_hinder_widget,
        validator=existing_userids
    )
    role = colander.SchemaNode(
        colander.String(),
        title=_('Role'),
        widget=deform.widget.SelectWidget(values=ROLE_CHOICES),
    )


class MembersSequence(colander.SequenceSchema):
    member = MemberSchema(title=_('Member'))


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

    def get_users_with_role(self, members, role):
        return set([m['user'] for m in members if m['role'] == role])

    def __call__(self, form, value):
        exc = colander.Invalid(form, 'Error when selecting group members')
        primaries = self.get_users_with_role(value['members'], 'primary')
        standins = self.get_users_with_role(value['members'], 'standin')
        if primaries.intersection(standins):
            exc['members'] = _('Same person can not be both primary and stand-in.')
        for grp in self.groups.values():
            if grp == self.group:
                continue
            grp_primaries = set(grp.primaries)
            intersect = primaries.intersection(grp_primaries)
            if intersect:
                exc['members'] = _('User(s) ${users} is already primary in other group.',
                                     mapping={'users': ', '.join(intersect)})

        for user_id in self.group.assignments.keys():
            if user_id not in primaries:
                exc['members'] = _('Cannot remove users with transferred voter permission.')
        for user_id in self.group.assignments.values():
            if user_id not in standins:
                exc['members'] = _('Cannot remove users with transferred voter permission.')

        if len(exc.children):
            raise exc


class EditMeetingVoteGroupSchema(colander.Schema):
    title = colander.SchemaNode(
        colander.String(),
        title=_("Title"),
    )
    description = colander.SchemaNode(
        colander.String(),
        title=_("Description"),
        missing="",
        widget=deform.widget.TextAreaWidget(),
    )
    members = MembersSequence(
        title=_("Vote group members"),
        description=_("Add one UserID per row."),
    )
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
    config.add_schema('MeetingVoteGroup', EditMeetingVoteGroupSchema, 'edit')
