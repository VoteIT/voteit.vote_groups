from unittest import TestCase

from pyramid import testing
from zope.interface.verify import verifyClass
from zope.interface.verify import verifyObject

from voteit.vote_groups.interfaces import IVoteGroup
from voteit.vote_groups.interfaces import IVoteGroups


class VoteGroupsTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    @property
    def _cut(self):
        from voteit.vote_groups.models import VoteGroups
        return VoteGroups

    def _mk_one(self):
        from voteit.core.models.meeting import Meeting
        return self._cut(Meeting())

    def test_verify_class(self):
        self.assertTrue(verifyClass(IVoteGroups, self._cut))

    def test_verify_obj(self):
        self.assertTrue(verifyObject(IVoteGroups, self._mk_one()))

    def test_xxx(self):
        #FIXME:
        pass


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
        return self._cut(Meeting())

    def test_verify_class(self):
        self.assertTrue(verifyClass(IVoteGroup, self._cut))

    def test_verify_obj(self):
        self.assertTrue(verifyObject(IVoteGroup, self._mk_one()))

    def test_xxx(self):
        #FIXME:
        pass