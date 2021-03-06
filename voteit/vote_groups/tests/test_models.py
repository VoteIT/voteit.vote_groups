from __future__ import unicode_literals

from unittest import TestCase

from BTrees.OOBTree import OOBTree
from pyramid import testing
from pyramid.request import apply_request_extensions
from voteit.vote_groups.exceptions import GroupPermissionsException

from voteit.core.models.interfaces import IMeeting
from voteit.core.testing_helpers import bootstrap_and_fixture
from zope.interface.verify import verifyClass
from zope.interface.verify import verifyObject

from voteit.vote_groups.interfaces import IAssignmentChanged
from voteit.vote_groups.interfaces import IVoteGroup
from voteit.vote_groups.interfaces import IVoteGroups
from voteit.vote_groups.interfaces import ROLE_PRIMARY
from voteit.vote_groups.interfaces import ROLE_STANDIN


class VoteGroupsTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    @property
    def _cut(self):
        from voteit.vote_groups.models import VoteGroups
        return VoteGroups

    def _initial_groups(self, groups):
        name = groups.new('g1')
        group = groups[name]
        group['one'] = ROLE_STANDIN
        group['two'] = ROLE_PRIMARY
        group['three'] = ROLE_STANDIN
        groups.assign_vote('two', 'one', group)
        name = groups.new('g2')
        group = groups[name]
        group['three'] = ROLE_PRIMARY

    def _mk_one(self):
        from voteit.core.models.meeting import Meeting
        groups = self._cut(Meeting(), testing.DummyRequest())
        self._initial_groups(groups)
        return groups

    def test_verify_class(self):
        self.assertTrue(verifyClass(IVoteGroups, self._cut))

    def test_verify_obj(self):
        self.assertTrue(verifyObject(IVoteGroups, self._mk_one()))

    def test_copy_from_meeting(self):
        from voteit.core.models.meeting import Meeting
        self.config.registry.registerAdapter(self._cut, provided=IVoteGroups)
        old_groups = self._mk_one()
        new_groups = self._cut(Meeting(), testing.DummyRequest())
        self.assertIsInstance(old_groups.context, Meeting)
        new_groups.copy_from_meeting(old_groups.context)
        self.assertEqual(len(new_groups), 2)

    def test_standins(self):
        groups = self._mk_one()
        self.assertEqual(groups.get_standin_for('two'), 'one')

    def test_members(self):
        groups = self._mk_one()
        self.assertEqual(groups.get_members(), {'one', 'two', 'three'})

    def test_voters(self):
        groups = self._mk_one()
        self.assertEqual(groups.get_voters(), {'one', 'three'})

    def test_primaries(self):
        groups = self._mk_one()
        self.assertEqual(groups.get_primaries(), {'two', 'three'})

    def test_nonzero(self):
        groups = self._mk_one()
        self.assertTrue(groups)

    def test_group_count(self):
        groups = self._mk_one()
        self.assertEqual(len(groups.sorted()), 2)
        self.assertEqual(len(groups.vote_groups_for_user('one')), 1)
        self.assertEqual(len(groups.vote_groups_for_user('two')), 1)
        self.assertEqual(len(groups.vote_groups_for_user('three')), 2)

    def test_free_standins(self):
        groups = self._mk_one()
        name = groups.new()
        group = groups[name]
        group['four'] = ROLE_PRIMARY
        group['five'] = ROLE_STANDIN
        group['one'] = ROLE_STANDIN
        self.assertEqual(groups.voters, {'one', 'three', 'four'})
        self.assertEqual(groups.get_free_standins(group), {'five'})

    def test_get_primary_for(self):
        groups = self._mk_one()
        primary, group = groups.get_primary_for('one')
        self.assertEqual(primary, 'two')
        self.assertEqual((None, None), groups.get_primary_for('two'))

    def test_get_voting_group_for(self):
        groups = self._mk_one()
        group1 = groups.get_voting_group_for('one')
        group3 = groups.get_voting_group_for('three')
        self.assertEqual(len(group1), 3)
        self.assertEqual(len(group3), 1)

    def test_assign_vote(self):
        groups = self._mk_one()
        group = groups.values()[0]
        group['four'] = ROLE_PRIMARY
        with self.assertRaises(GroupPermissionsException):
            groups.assign_vote('four', 'one', group)

    def test_set_role(self):
        groups = self._mk_one()
        name = groups.new()
        group = groups[name]
        group['one'] = ROLE_STANDIN
        group['four'] = ROLE_STANDIN
        with self.assertRaises(AssertionError):
            groups.set_role('one', 'badness', group)
        with self.assertRaises(GroupPermissionsException):
            groups.set_role('two', ROLE_PRIMARY, group)

    def test_assign_permission(self):
        groups = self._mk_one()
        self.config.testing_securitypolicy(
            userid='one', permissive=True
        )
        group = groups['g1']
        groups.request.is_moderator = False

        self.assertTrue(groups.get_assign_permission('one', group))
        self.assertFalse(groups.get_assign_permission('two', group))
        self.assertFalse(groups.get_assign_permission('three', group))

        self.config.testing_securitypolicy(
            userid='two', permissive=True
        )
        self.assertFalse(groups.get_assign_permission('one', group))
        self.assertTrue(groups.get_assign_permission('two', group))
        self.assertFalse(groups.get_assign_permission('three', group))

        groups.request.is_moderator = True
        self.assertTrue(groups.get_assign_permission('one', group))
        self.assertFalse(groups.get_assign_permission('three', group))

    def test_release_substitute_is_moderator(self):
        events = []

        def subscriber(event):
            events.append(event)
        self.config.add_subscriber(subscriber, IAssignmentChanged)

        groups = self._mk_one()
        groups.request.is_moderator = True
        group = groups['g1']

        self.assertIs(groups.release_substitute('one', group), None)
        self.assertEqual(len(events), 2)
        with self.assertRaises(GroupPermissionsException):
            groups.release_substitute('one', group)
        self.assertEqual(len(events), 2)

    def test_release_substitute_is_standin(self):
        self.config.testing_securitypolicy(
            userid='one', permissive=True
        )
        groups = self._mk_one()
        groups.request.is_moderator = False
        group = groups['g1']
        self.assertIs(groups.release_substitute('one', group), None)

    def test_set_role_event(self):
        events = []

        def subscriber(event):
            events.append(event)
        self.config.add_subscriber(subscriber, IAssignmentChanged)

        groups = self._mk_one()  # Vote assigned, fires one event
        name = groups.new()
        group = groups[name]
        group['five'] = ROLE_STANDIN
        groups.set_role('five', ROLE_PRIMARY, group)  # Role assigned, fires one event
        self.assertEqual(len(events), 2)
        self.assertNotEqual(events[0].group, group)
        self.assertEqual(events[1].group, group)

    def test_get_emails(self):
        from arche.resources import User
        from voteit.core.models.meeting import Meeting
        from voteit.vote_groups.models import VoteGroups
        self.config.include('arche.testing')
        self.config.include('voteit.core.testing_helpers.register_catalog')
        root = bootstrap_and_fixture(self.config)
        request = testing.DummyRequest()
        apply_request_extensions(request)
        request.root = root
        self.config.begin(request)
        root['m'] = m = Meeting()
        root['users']['one'] = User(email='hello@world.org', email_validated=True)

        groups = VoteGroups(m, request)
        self._initial_groups(groups)
        group = groups.values()[0]
        group.potential_members.add('support@voteit.se')

        self.assertEqual(groups.get_emails(), {'support@voteit.se', 'hello@world.org'})

    def test_traversal(self):
        groups = self._mk_one()
        name = groups.new()
        group = groups[name]
        self.failUnless(IMeeting.providedBy(group.__parent__))

    def test_settings(self):
        groups = self._mk_one()
        groups.settings = {'hello': 'world'}
        self.assertEqual({'hello': 'world'}, groups.settings)
        self.assertIsInstance(groups.context._vote_groups_settings, OOBTree)

    def test_repr(self):
        groups = self._mk_one()
        self.assertIn('<voteit.vote_groups.models.VoteGroups adapter', repr(groups))

    def test_from_appstruct(self):
        from arche.resources import User
        from voteit.core.models.meeting import Meeting
        from voteit.core import security
        from voteit.vote_groups.models import VoteGroups
        from voteit.vote_groups.models import adjust_roles_after_assignment
        self.config.add_subscriber(adjust_roles_after_assignment, IAssignmentChanged)
        self.config.registry.registerAdapter(VoteGroups, provided=IVoteGroups)
        self.config.include('arche.testing')
        self.config.include('voteit.core.testing_helpers.register_catalog')
        root = bootstrap_and_fixture(self.config)
        request = testing.DummyRequest()
        apply_request_extensions(request)
        request.root = root
        self.config.begin(request)
        root['m'] = m = Meeting()
        root['users']['one'] = User(email='hello@world.org', email_validated=True)

        groups = VoteGroups(m, request)
        groups.settings = {
            'assigned_voter_roles': {security.VIEW, security.ADD_PROPOSAL},
            'inactive_voter_roles': {security.VIEW},
        }
        self._initial_groups(groups)
        group = groups['g1']
        groups.update_from_appstruct({
            'title': 'Monty',
            'description': 'python3',
            'members': [
                'zero',
                'two',
            ],
            'potential_members': 'support@voteit.se\nhello@world.org',
        }, group)
        self.assertEqual(group.title, 'Monty')
        self.assertEqual(group.description, 'python3')
        self.assertEqual(set(group.keys()), {'zero', 'one', 'two'})
        self.assertEqual(set(group.potential_members), {'support@voteit.se'})


class VoteGroupTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    @property
    def _cut(self):
        from voteit.vote_groups.models import VoteGroup
        return VoteGroup

    def _mk_one(self):
        from voteit.core.models.meeting import Meeting
        from voteit.vote_groups.models import VoteGroups
        groups = VoteGroups(Meeting(), testing.DummyRequest())
        name = groups.new()
        group = groups[name]
        group['one'] = 'standin'
        group['two'] = 'primary'
        group['three'] = 'standin'
        group.potential_members.add('test@example.com')
        group.potential_members.add('support@voteit.se')
        return group

    def test_verify_class(self):
        self.assertTrue(verifyClass(IVoteGroup, self._cut))

    def test_verify_obj(self):
        self.assertTrue(verifyObject(IVoteGroup, self._mk_one()))

    def test_members(self):
        group = self._mk_one()
        self.assertEqual(set(group.keys()), {'one', 'two', 'three'})
        self.assertEqual(set(group.primaries), {'two'})
        self.assertEqual(group.get_voters(), {'two'})

    def test_assignments(self):
        group = self._mk_one()
        group.assignments['two'] = 'one'
        self.assertEqual(group.get_voters(), {'one'})
        self.assertEqual(group.get_primary_for('one'), 'two')
        self.assertIs(group.get_primary_for('two'), None)
        self.assertEqual(group.get_substitute_for('two'), 'one')
        self.assertIs(group.get_substitute_for('one'), None)

    def test_appstruct(self):
        group = self._mk_one()
        appstruct = group.appstruct()
        self.assertIsInstance(appstruct, dict)
        self.assertEqual(len(appstruct['members']), 3)
        self.assertEqual(appstruct['potential_members'].split('\n'), ['support@voteit.se', 'test@example.com'])


class UserValidatedEmailIntegrationTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def test_email_validated_subscriber(self):
        from arche.events import EmailValidatedEvent
        from arche.resources import User
        from voteit.core.models.meeting import Meeting
        from voteit.vote_groups.models import VoteGroups
        self.config.include('arche.testing')
        self.config.include('voteit.core.testing_helpers.register_catalog')
        root = bootstrap_and_fixture(self.config)
        request = testing.DummyRequest()
        apply_request_extensions(request)
        request.root = root
        self.config.begin(request)
        root['m'] = m = Meeting()
        root['users']['jane'] = user = User(email='hello@world.org', email_validated=True)
        groups = VoteGroups(m, request)
        name = groups.new()
        group = groups[name]
        group.potential_members.add('hello@world.org')
        self.config.include('voteit.vote_groups.models')
        event = EmailValidatedEvent(user)
        self.config.registry.notify(event)
        # Should have been picked up
        self.assertNotIn('hello@world.org', group.potential_members)
        # And added
        self.assertIn('jane', group)
