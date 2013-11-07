"""
Pyramid views for Eucalyptus and AWS volumes

"""
from pyramid.view import view_config

from ..models import LandingPageFilter
from ..models.volumes import Volume
from ..views import LandingPageView


class VolumesView(LandingPageView):
    def __init__(self, request):
        super(VolumesView, self).__init__(request)
        self.items = Volume.fakeall()
        self.initial_sort_key = '-create_time'
        self.prefix = '/volumes'

    @view_config(route_name='volumes', renderer='../templates/volumes/volumes.pt')
    def volumes_landing(self):
        json_items_endpoint = self.request.route_url('volumes_json')
        status_choices = sorted(set(item.get('status') for item in self.items))
        avail_zone_choices = sorted(set(item.get('availability_zone') for item in self.items))
        # Filter fields are passed to 'properties_filter_form' template macro to display filters at left
        self.filter_fields = [
            LandingPageFilter(key='status', name='Status', choices=status_choices),
            LandingPageFilter(key='availability_zone', name='Availability zone', choices=avail_zone_choices),
            # LandingPageFilter(key='tags', name='Tags'),
        ]
        more_filter_keys = ['id', 'name', 'size', 'instance', 'snapshot', 'create_time', 'tags']
        # filter_keys are passed to client-side filtering in search box
        self.filter_keys = [field.key for field in self.filter_fields] + more_filter_keys

        return dict(
            display_type=self.display_type,
            filter_fields=self.filter_fields,
            filter_keys=self.filter_keys,
            prefix=self.prefix,
            initial_sort_key=self.initial_sort_key,
            json_items_endpoint=json_items_endpoint,
        )

    @view_config(route_name='volumes_json', renderer='json', request_method='GET')
    def volumes_json(self):
        return dict(results=self.items)
