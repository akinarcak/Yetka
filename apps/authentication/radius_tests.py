# -*- coding: utf-8 -*-
#
"""Tests for this project's own RADIUS backend behaviour.

The RADIUS path had no coverage at all until the django-radius dependency was
moved off a fork and onto upstream. The library provides the protocol work; what
is asserted here is the part this project overrides, because that is what the
swap could quietly change.

The library's own `get_django_user` assigns `is_staff` and `is_superuser` from
the RADIUS reply's `Class` attribute. `CreateUserMixin` replaces that method and
discards those arguments, so a RADIUS server cannot grant Django privileges
here. That property depends on the method resolution order and on a signature
that swallows the arguments; both are asserted below so a future dependency
bump cannot restore the library's behaviour unnoticed.
"""
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

User = get_user_model()


def _backends():
    """Import lazily.

    Importing the RADIUS backend at module scope pulls in radiusauth during test
    discovery, which happens before setup_databases. That reliably broke test
    database creation while applying users.0001_initial, so the import is
    deferred until a test actually needs it.
    """
    from authentication.backends.radius.backends import (
        CreateUserMixin,
        RadiusBackend,
        RadiusRealmBackend,
    )

    return CreateUserMixin, RadiusBackend, RadiusRealmBackend


@override_settings(EMAIL_SUFFIX='radius.example.com')
class RadiusUserCreationTests(TestCase):
    def test_existing_user_is_returned_without_creating_another(self):
        existing = User.objects.create(
            username='someone', name='someone', email='someone@elsewhere.test'
        )

        user = _backends()[0].get_django_user('someone')

        self.assertEqual(user.pk, existing.pk)
        self.assertEqual(user.email, 'someone@elsewhere.test')
        self.assertEqual(User.objects.filter(username='someone').count(), 1)

    def test_new_user_gets_the_configured_email_suffix(self):
        user = _backends()[0].get_django_user('newcomer')

        self.assertEqual(user.username, 'newcomer')
        self.assertEqual(user.name, 'newcomer')
        self.assertEqual(user.email, 'newcomer@radius.example.com')

    def test_username_that_is_already_an_address_is_used_as_the_email(self):
        user = _backends()[0].get_django_user('person@corp.test')

        self.assertEqual(user.email, 'person@corp.test')

    def test_bytes_username_is_decoded(self):
        user = _backends()[0].get_django_user(b'bytesuser')

        self.assertEqual(user.username, 'bytesuser')
        self.assertEqual(User.objects.filter(username='bytesuser').count(), 1)

    def test_creation_notifies_the_radius_signal(self):
        with patch(
            'authentication.backends.radius.backends.radius_create_user'
        ) as signal:
            user = _backends()[0].get_django_user('signalled')

        signal.send.assert_called_once()
        self.assertEqual(signal.send.call_args.kwargs['user'], user)

    def test_existing_user_does_not_notify_the_signal(self):
        User.objects.create(username='quiet', name='quiet', email='quiet@x.test')

        with patch(
            'authentication.backends.radius.backends.radius_create_user'
        ) as signal:
            _backends()[0].get_django_user('quiet')

        signal.send.assert_not_called()


@override_settings(EMAIL_SUFFIX='radius.example.com')
class RadiusRemotePrivilegeTests(TestCase):
    """A RADIUS server must not be able to grant privileges.

    `is_staff` is deliberately not asserted here. On this project's user model
    it is a derived property -- `is_authenticated and is_valid` -- with a setter
    that does nothing, so it is true for every valid user and false for none.
    Asserting it false fails for reasons that have nothing to do with RADIUS and
    would say nothing if it passed. `is_superuser` is the one that carries
    privilege: it is true only when the user holds the system administrator
    role, so it does answer whether a RADIUS reply reached anything.
    """

    def test_remote_roles_are_discarded_for_a_new_user(self):
        user = _backends()[0].get_django_user(
            'elevated',
            None,
            ['admins'],
            True,
            True,
        )

        self.assertFalse(user.is_superuser)
        self.assertFalse(user.system_roles.filter(name='SystemAdmin').exists())

    def test_remote_roles_are_discarded_for_an_existing_user(self):
        User.objects.create(
            username='plain', name='plain', email='plain@x.test'
        )

        user = _backends()[0].get_django_user(
            'plain', None, groups=['admins'], is_staff=True, is_superuser=True
        )

        self.assertFalse(user.is_superuser)
        self.assertFalse(user.system_roles.filter(name='SystemAdmin').exists())

    def test_backends_resolve_to_the_overriding_implementation(self):
        # The library's get_django_user is what applies is_staff/is_superuser.
        # If a dependency bump ever moved this project's override out of the
        # way, the two assertions above would still pass while the real backend
        # started honouring remote roles.
        CreateUserMixin, RadiusBackend, RadiusRealmBackend = _backends()
        for backend in (RadiusBackend, RadiusRealmBackend):
            with self.subTest(backend=backend.__name__):
                self.assertEqual(
                    backend.get_django_user.__qualname__,
                    'CreateUserMixin.get_django_user',
                )
                defining = [
                    klass
                    for klass in backend.__mro__
                    if 'get_django_user' in klass.__dict__
                ]
                self.assertIs(defining[0], CreateUserMixin)


class RadiusClassAttributeDecodingTests(TestCase):
    """The mixin swallows a UnicodeError raised while decoding `Class`.

    Upstream may fix this; the workaround must keep failing closed until it
    does, rather than letting the error reach the caller as an auth crash.
    """

    def _backend(self, fail_in_cl_decode=False, return_value=None):
        class Stub:
            def _perform_radius_auth(self, client, packet):
                if fail_in_cl_decode:
                    # The workaround identifies the library's bug by finding
                    # the text `cl.decode` in the traceback, and it formats
                    # that traceback with limit=2. So the failure has to be
                    # raised here, one frame below the caller, by a line that
                    # really reads `cl.decode`. Capturing the error elsewhere
                    # and re-raising it does not work: the re-raise pushes the
                    # original frame past the limit and the text is never seen.
                    cl = b'\xff'
                    return cl.decode('utf-8')
                return return_value

        CreateUserMixin = _backends()[0]

        class Backend(CreateUserMixin, Stub):
            pass

        return Backend()

    def test_class_decode_unicode_error_is_swallowed(self):
        backend = self._backend(fail_in_cl_decode=True)

        self.assertEqual(
            backend._perform_radius_auth(Mock(), Mock()), ([], False, False)
        )

    def test_unicode_error_from_elsewhere_is_not_swallowed(self):
        # The workaround must stay narrow. A UnicodeError raised anywhere other
        # than the library's `cl.decode` is a different fault and returns None
        # rather than a successful-looking empty result.
        class Stub:
            def _perform_radius_auth(self, client, packet):
                raise UnicodeError('unrelated')

        CreateUserMixin = _backends()[0]

        class Backend(CreateUserMixin, Stub):
            pass

        self.assertIsNone(Backend()._perform_radius_auth(Mock(), Mock()))

    def test_successful_auth_is_passed_through(self):
        backend = self._backend(return_value=(['group'], True, False))

        self.assertEqual(
            backend._perform_radius_auth(Mock(), Mock()), (['group'], True, False)
        )


class RadiusBackendEnablementTests(TestCase):
    @override_settings(AUTH_RADIUS=True)
    def test_enabled_when_configured(self):
        _, RadiusBackend, RadiusRealmBackend = _backends()
        self.assertTrue(RadiusBackend.is_enabled())
        self.assertTrue(RadiusRealmBackend.is_enabled())

    @override_settings(AUTH_RADIUS=False)
    def test_disabled_when_not_configured(self):
        _, RadiusBackend, RadiusRealmBackend = _backends()
        self.assertFalse(RadiusBackend.is_enabled())
        self.assertFalse(RadiusRealmBackend.is_enabled())
