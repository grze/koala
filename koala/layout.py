# -*- coding: utf-8 -*-
"""
Layout configuration via pyramid_layout
See http://docs.pylonsproject.org/projects/pyramid_layout/en/latest/layouts.html

"""
from collections import namedtuple
from urlparse import urlparse

from beaker.cache import cache_region
from pyramid.decorator import reify
from pyramid.httpexceptions import HTTPNotFound
from pyramid.i18n import TranslationString as _
from pyramid.renderers import get_renderer
from pyramid.settings import asbool

from .constants import AWS_REGIONS
from .models import Notification


class MasterLayout(object):
    site_title = "Eucalyptus Management Console"

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.home_url = request.application_url
        self.help_url = request.registry.settings.get('help.url')
        self.support_url = request.registry.settings.get('support.url')
        self.aws_enabled = asbool(request.registry.settings.get('aws.enabled'))
        self.aws_regions = AWS_REGIONS
        self.default_region = request.registry.settings.get('aws.default.region')
        self.cloud_type = request.session.get('cloud_type')
        self.selected_region = self.request.session.get('region', self.default_region)
        self.selected_region_label = self.get_selected_region_label(self.selected_region)
        self.username = self.request.session.get('username')
        self.account = self.request.session.get('account')
        self.username_label = self.request.session.get('username_label')
        self.tableview_url = self.get_datagridview_url('tableview')
        self.gridview_url = self.get_datagridview_url('gridview')
        self.date_format = _(u'%H:%M:%S %p %b %d %Y')
        self.angular_date_format = _(u'hh:mm:ss a MMM d yyyy')
        self.tag_pattern = '^(?!aws:).*'
        self.cidr_pattern = '{0}{1}'.format(
            '^((25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])\.){3}',
            '(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])(\/\d+)$'
        )

    def get_notifications(self):
        """Get notifications, categorized by message type ('info', 'success', 'warning', or 'error')
        To add a success notification, use self.request.session.flash(msg, 'success')
        See http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/sessions.html#using-the-session-flash-method
        """
        notifications = []
        notification = namedtuple('Notification', ['message', 'type', 'style'])
        for queue in Notification.TYPES:
            for notice in self.request.session.pop_flash(queue=queue):
                notifications.append(
                    notification(message=notice, type=queue, style=Notification.FOUNDATION_STYLES.get(queue)))
        # Add custom error messages via self.request.error_messages = [message_1, message_2, ...] in the view
        error_messages = getattr(self.request, 'error_messages', [])
        for error in error_messages:
            queue = Notification.ERROR
            notifications.append(
                notification(message=error, type=queue, style=Notification.FOUNDATION_STYLES.get(queue))
            )
        return notifications

    def get_datagridview_url(self, display):
        """Convenience property to get tableview or gridview URL for landing pages"""
        try:
            current_url = self.request.current_route_url()
        except ValueError:
            # Handle "ValueError: Current request matches no route" errors
            return HTTPNotFound()
        parsed_url = urlparse(current_url)
        otherview = 'gridview' if display == 'tableview' else 'tableview'
        if 'launch' in parsed_url.query:
            current_url = current_url.replace('?launch=1', '')
        if 'display' in parsed_url.query:
            return current_url.replace(otherview, display)
        else:
            ampersand = '&' if '?' in current_url else '?'
            return '{url}{amp}display={view}'.format(url=current_url, amp=ampersand, view=display)

    @staticmethod
    @cache_region('extra_long_term', 'selected_region_label')
    def get_selected_region_label(region_name):
        """Get the label from the selected region, pulling from Beaker cache"""
        regions = [reg for reg in AWS_REGIONS if reg.get('name') == region_name]
        if regions:
            return regions[0].get('label')
        return ''

    @reify
    def global_macros(self):
        renderer = get_renderer("templates/macros.pt")
        return renderer.implementation().macros
