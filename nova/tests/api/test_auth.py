# Copyright (c) 2012 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
import webob
import webob.exc

import nova.api.auth
from nova.openstack.common.gettextutils import _
from nova import test


class TestNovaKeystoneContextMiddleware(test.TestCase):

    def setUp(self):
        super(TestNovaKeystoneContextMiddleware, self).setUp()

        @webob.dec.wsgify()
        def fake_app(req):
            self.context = req.environ['nova.context']
            return webob.Response()

        self.context = None
        self.middleware = nova.api.auth.NovaKeystoneContext(fake_app)
        self.request = webob.Request.blank('/')
        self.request.headers['X_TENANT_ID'] = 'testtenantid'
        self.request.headers['X_AUTH_TOKEN'] = 'testauthtoken'
        self.request.headers['X_SERVICE_CATALOG'] = json.dumps({})

    def test_no_user_or_user_id(self):
        response = self.request.get_response(self.middleware)
        self.assertEqual(response.status, '401 Unauthorized')

    def test_user_only(self):
        self.request.headers['X_USER_ID'] = 'testuserid'
        response = self.request.get_response(self.middleware)
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(self.context.user_id, 'testuserid')

    def test_user_id_only(self):
        self.request.headers['X_USER'] = 'testuser'
        response = self.request.get_response(self.middleware)
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(self.context.user_id, 'testuser')

    def test_user_id_trumps_user(self):
        self.request.headers['X_USER_ID'] = 'testuserid'
        self.request.headers['X_USER'] = 'testuser'
        response = self.request.get_response(self.middleware)
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(self.context.user_id, 'testuserid')

    def test_invalid_service_catalog(self):
        self.request.headers['X_USER'] = 'testuser'
        self.request.headers['X_SERVICE_CATALOG'] = "bad json"
        response = self.request.get_response(self.middleware)
        self.assertEqual(response.status, '500 Internal Server Error')


class TestKeystoneMiddlewareRoles(test.TestCase):

    def setUp(self):
        super(TestKeystoneMiddlewareRoles, self).setUp()

        @webob.dec.wsgify()
        def role_check_app(req):
            context = req.environ['nova.context']

            if "knight" in context.roles and "bad" not in context.roles:
                return webob.Response(status=_("200 Role Match"))
            elif context.roles == ['']:
                return webob.Response(status=_("200 No Roles"))
            else:
                raise webob.exc.HTTPBadRequest(_("unexpected role header"))

        self.middleware = nova.api.auth.NovaKeystoneContext(role_check_app)
        self.request = webob.Request.blank('/')
        self.request.headers['X_USER'] = 'testuser'
        self.request.headers['X_TENANT_ID'] = 'testtenantid'
        self.request.headers['X_AUTH_TOKEN'] = 'testauthtoken'
        self.request.headers['X_SERVICE_CATALOG'] = json.dumps({})

        self.roles = "pawn, knight, rook"

    def test_roles(self):
        # Test that the newer style role header takes precedence.
        self.request.headers['X_ROLES'] = 'pawn,knight,rook'
        self.request.headers['X_ROLE'] = 'bad'

        response = self.request.get_response(self.middleware)
        self.assertEqual(response.status, '200 Role Match')

    def test_roles_empty(self):
        self.request.headers['X_ROLES'] = ''
        response = self.request.get_response(self.middleware)
        self.assertEqual(response.status, '200 No Roles')

    def test_deprecated_role(self):
        # Test fallback to older role header.
        self.request.headers['X_ROLE'] = 'pawn,knight,rook'

        response = self.request.get_response(self.middleware)
        self.assertEqual(response.status, '200 Role Match')

    def test_role_empty(self):
        self.request.headers['X_ROLE'] = ''
        response = self.request.get_response(self.middleware)
        self.assertEqual(response.status, '200 No Roles')

    def test_no_role_headers(self):
        # Test with no role headers set.

        response = self.request.get_response(self.middleware)
        self.assertEqual(response.status, '200 No Roles')
