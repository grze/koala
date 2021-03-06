# -*- coding: utf-8 -*-
"""
Pyramid views for Login/Logout

"""
import base64
from urllib2 import HTTPError, URLError
from urlparse import urlparse

from pyramid.httpexceptions import HTTPFound
from pyramid.i18n import TranslationString as _
from pyramid.security import NO_PERMISSION_REQUIRED, remember, forget
from pyramid.settings import asbool
from pyramid.view import view_config, forbidden_view_config

from ..forms.login import EucaLoginForm, AWSLoginForm
from ..models.auth import AWSAuthenticator, EucaAuthenticator, ConnectionManager
from ..views import BaseView


@forbidden_view_config()
def redirect_to_login_page(request):
    login_url = request.route_url('login')
    return HTTPFound(login_url)


class LoginView(BaseView):
    TEMPLATE = '../templates/login.pt'

    def __init__(self, request):
        super(LoginView, self).__init__(request)
        self.request = request
        self.euca_login_form = EucaLoginForm(self.request, formdata=self.request.params or None)
        self.aws_login_form = AWSLoginForm(self.request, formdata=self.request.params or None)
        self.aws_enabled = asbool(request.registry.settings.get('enable.aws'))
        referrer = self.request.url
        login_url = self.request.route_url('login')
        logout_url = self.request.route_url('logout')
        if referrer in [login_url, logout_url]:
            referrer = '/'  # never use the login form (or logout view) itself as came_from
        came_from_param = self.request.params.get('came_from', referrer)
        self.came_from = urlparse(came_from_param).path or '/'
        self.login_form_errors = []
        self.duration = str(int(self.request.registry.settings.get('session.cookie_expires'))+60)
        self.https_required = asbool(self.request.registry.settings.get('session.secure', False))
        self.render_dict = dict(
            https_required=self.https_required,
            euca_login_form=self.euca_login_form,
            aws_login_form=self.aws_login_form,
            login_form_errors=self.login_form_errors,
            aws_enabled=self.aws_enabled,
            duration=self.duration,
            came_from=self.came_from,
        )

    @view_config(route_name='login', request_method='GET', renderer=TEMPLATE, permission=NO_PERMISSION_REQUIRED)
    @forbidden_view_config(request_method='GET', renderer=TEMPLATE)
    def login_page(self):
        return self.render_dict

    @view_config(route_name='login', request_method='POST', renderer=TEMPLATE, permission=NO_PERMISSION_REQUIRED)
    def handle_login(self):
        """Handle login form post"""

        login_type = self.request.params.get('login_type')

        if login_type == 'Eucalyptus':
            return self.handle_euca_login()
        elif login_type == 'AWS':
            return self.handle_aws_login()

        return self.render_dict

    def handle_euca_login(self):
        new_passwd = None
        clchost = self.request.registry.settings.get('clchost')
        auth = EucaAuthenticator(host=clchost, duration=self.duration)
        session = self.request.session

        if self.euca_login_form.validate():
            account = self.request.params.get('account')
            username = self.request.params.get('username')
            password = self.request.params.get('password')
            try:
                creds = auth.authenticate(
                    account=account, user=username, passwd=password, new_passwd=new_passwd, timeout=8)
                user_account = '{user}@{account}'.format(user=username, account=account)
                self.invalidate_cache()  # Clear connection objects from cache
                session.invalidate()  # Refresh session
                session['cloud_type'] = 'euca'
                session['account'] = account
                session['username'] = username
                session['session_token'] = creds.session_token
                session['access_id'] = creds.access_key
                session['secret_key'] = creds.secret_key
                session['username_label'] = '{user}@{account}'.format(user=username, account=account)
                headers = remember(self.request, user_account)
                return HTTPFound(location=self.came_from, headers=headers)
            except HTTPError, err:
                if err.code == 403:  # password expired
                    changepwd_url = self.request.route_url('changepassword')
                    return HTTPFound(changepwd_url+("?expired=true&account=%s&username=%s" % (account, username)))
                elif err.msg == u'Unauthorized':
                    msg = _(u'Invalid user/account name and/or password.')
                    self.login_form_errors.append(msg)
            except URLError, err:
                if str(err.reason) == 'timed out':
                    msg = _(u'No response from host ')
                    self.login_form_errors.append(msg + clchost)
        return self.render_dict

    def handle_aws_login(self):
        session = self.request.session
        if self.aws_login_form.validate():
            package = self.request.params.get('package')
            package = base64.decodestring(package);
            try:
                auth = AWSAuthenticator(package=package)
                creds = auth.authenticate(timeout=10)
                default_region = self.request.registry.settings.get('aws.default.region', 'us-east-1')
                self.invalidate_cache()  # Clear connection objects from cache
                session.invalidate()  # Refresh session
                session['cloud_type'] = 'aws'
                session['session_token'] = creds.session_token
                session['access_id'] = creds.access_key
                session['secret_key'] = creds.secret_key
                session['region'] = default_region
                session['username_label'] = '{user}...@AWS'.format(user=creds.access_key[:8])
                # Save EC2 Connection object in cache
                ConnectionManager.aws_connection(
                    default_region, creds.access_key, creds.secret_key, creds.session_token, 'ec2')
                headers = remember(self.request, creds.access_key[:8])
                return HTTPFound(location=self.came_from, headers=headers)
            except HTTPError, err:
                if err.msg == 'Forbidden':
                    msg = _(u'Invalid access key and/or secret key.')
                    self.login_form_errors.append(msg)
        return self.render_dict


class LogoutView(BaseView):
    def __init__(self, request):
        super(LogoutView, self).__init__(request)
        self.request = request
        self.login_url = request.route_url('login')

    @view_config(route_name='logout', request_method='POST')
    def logout(self):
        forget(self.request)
        self.request.session.invalidate()
        self.invalidate_cache()
        return HTTPFound(location=self.login_url)

