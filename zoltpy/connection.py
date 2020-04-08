import json
import logging
from abc import ABC

import requests


logger = logging.getLogger(__name__)


class ZoltarConnection:
    """
    Represents a connection to a Zoltar server. This is an object-oriented interface that may be best suited to zoltpy
    developers. See the `util` module for a name-based non-OOP interface.

    A note on URLs: We require a trailing slash ('/') on all URLs. The only exception is the host arg passed to this
    class's constructor. This convention matches Django REST framework one, which is what Zoltar is written in.

    Notes:
    - This implementation uses the simple approach of caching the JSON response for resource URLs, but doesn't
      automatically handle their becoming stale, hence the need to call ZoltarResource.refresh().
    """


    def __init__(self, host='https://zoltardata.com'):
        """
        :param host: URL of the Zoltar host. should *not* have a trailing '/'
        """
        self.host = host
        self.username, self.password = None, None
        self.session = None


    def authenticate(self, username, password):
        self.username, self.password = username, password
        self.session = ZoltarSession(self)


    def re_authenticate_if_necessary(self):
        if self.session.is_token_expired():
            logger.info(f"re_authenticate_if_necessary(): re-authenticating expired token. host={self.host}")
            self.authenticate(self.username, self.password)


    @property
    def projects(self):
        """
        The entry point into ZoltarResources.

        Returns a list of Projects. NB: A property, but hits the API.
        """
        projects_json_list = self.json_for_uri(self.host + '/api/projects/')
        return [Project(self, project_json['url'], project_json) for project_json in projects_json_list]


    def json_for_uri(self, uri):
        logger.info(f"json_for_uri(): {uri!r}")
        if not self.session:
            raise RuntimeError("json_for_uri(): no session")

        response = requests.get(uri, headers={'Accept': 'application/json; indent=4',
                                              'Authorization': 'JWT {}'.format(self.session.token)})
        if response.status_code != 200:  # HTTP_200_OK
            raise RuntimeError(f"json_for_uri(): status code was not 200. status_code={response.status_code}. "
                               f"text={response.text}")

        return response.json()


class ZoltarSession:  # internal use

    def __init__(self, zoltar_connection):
        super().__init__()
        self.zoltar_connection = zoltar_connection
        self.token = self._get_token()


    def _get_token(self):
        response = requests.post(self.zoltar_connection.host + '/api-token-auth/',
                                 {'username': self.zoltar_connection.username,
                                  'password': self.zoltar_connection.password})
        if response.status_code != 200:  # HTTP_200_OK
            raise RuntimeError(f"get_token(): status code was not 200. status_code={response.status_code}. "
                               f"text={response.text}")

        return response.json()['token']


    def is_token_expired(self):
        """
        :return: True if my token is expired, and False o/w
        """
        # see zoltr: is_token_expired(), token_expiration_date()
        return True  # todo xx fix!


class ZoltarResource(ABC):
    """
    An abstract proxy for a Zoltar object at a particular URI including its JSON. All it does is cache JSON from a URI.
    Notes:

    - This class and its subclasses are not meant to be directly instantiated by users. Instead the user enters through
      ZoltarConnection.projects and then drills down.
    - Because the JSON is cached, it will become stale after the source object in the server changes, such as when a new
      model is created or a forecast uploaded. This it's the user's responsibility to call `refresh()` as needed.
    - Newly-created instances do *not* refresh by default, for efficiency.
    """


    def __init__(self, zoltar_connection, uri, initial_json=None):
        """
        :param zoltar_connection:
        :param uri:
        :param initial_json: optional param that's passed if caller already has JSON from server
        """
        self.zoltar_connection = zoltar_connection
        self.uri = uri  # *does* include trailing slash
        self._json = initial_json  # cached JSON is None if not yet touched. can become stale
        # NB: no self.refresh() call!


    def __repr__(self):
        """
        A default __repr__() that does not hit the API unless my _json has been cached, in which case my _repr_keys
        class var is used to determine which properties to return.
        """
        repr_keys = getattr(self, '_repr_keys', None)
        repr_list = [self.__class__.__name__, self.uri, self.id]
        if repr_keys and self._json:
            repr_list.extend([self._json[repr_key] for repr_key in repr_keys if repr_key in self._json])
        return str(tuple(repr_list))


    @property
    def id(self):  # todo xx rename to not conflict with `id` builtin
        return ZoltarResource.id_for_uri(self.uri)


    @classmethod
    def id_for_uri(cls, uri):
        """
        :return: the trailing integer id from a url structured like: "http://example.com/api/forecast/71/" -> 71L
        """
        url_split = [split for split in uri.split('/') if split]  # drop any empty components, mainly from end
        return int(url_split[-1])


    @property
    def json(self):
        """
        :return: my json as a dict, refreshing if none cached yet
        """
        return self._json if self._json else self.refresh()


    def refresh(self):
        self._json = self.zoltar_connection.json_for_uri(self.uri)
        return self._json


    def delete(self):
        response = requests.delete(self.uri, headers={'Accept': 'application/json; indent=4',
                                                      'Authorization': f'JWT {self.zoltar_connection.session.token}'})
        if response.status_code != 204:  # HTTP_204_NO_CONTENT
            raise RuntimeError(f'delete_resource(): status code was not 204: {response.status_code}. {response.text}')


class Project(ZoltarResource):
    """
    Represents a Zoltar project, and is the entry point for getting its list of Models.
    """

    _repr_keys = ('name', 'is_public')


    def __init__(self, zoltar_connection, uri, initial_json=None):
        super().__init__(zoltar_connection, uri, initial_json)


    @property
    def name(self):
        return self.json['name']


    @property
    def models(self):
        """
        :return: a list of the Project's Models
        """
        models_json_list = self.zoltar_connection.json_for_uri(self.uri + 'models/')
        return [Model(self.zoltar_connection, model_json['url'], model_json) for model_json in models_json_list]


    @property
    def units(self):
        """
        :return: a list of the Project's Units
        """
        units_json_list = self.zoltar_connection.json_for_uri(self.uri + 'units/')
        return [Unit(self.zoltar_connection, unit_json['url'], unit_json) for unit_json in units_json_list]


    @property
    def targets(self):
        """
        :return: a list of the Project's Targets
        """
        targets_json_list = self.zoltar_connection.json_for_uri(self.uri + 'targets/')
        return [Target(self.zoltar_connection, target_json['url'], target_json) for target_json in targets_json_list]


    @property
    def timezeros(self):
        """
        :return: a list of the Project's TimeZeros
        """
        timezeros_json_list = self.zoltar_connection.json_for_uri(self.uri + 'timezeros/')
        return [TimeZero(self.zoltar_connection, timezero_json['url'], timezero_json)
                for timezero_json in timezeros_json_list]


    def create_model(self, model_config):
        """Creates a forecast Model with the passed configuration.

        :param model_config: a dict used to initialize the new model. it must contain these fields: ['name'], and can
            optionally contain: ['abbreviation', 'team_name', 'description', 'home_url', 'aux_data_url']
        :return: a Model
        """
        # validate model_config
        actual_keys = set(model_config.keys())
        expected_keys = {'name', 'abbreviation', 'team_name', 'description', 'home_url', 'aux_data_url'}
        if actual_keys != expected_keys:
            raise RuntimeError(f"Wrong keys in 'model_config'. expected={expected_keys}, actual={actual_keys}")

        # POST. note that we throw away the new model's JSON that's returned once we extract its pk b/c it will be
        # cached by the Model() call
        response = requests.post(f'{self.uri}models/',
                                 headers={'Authorization': f'JWT {self.zoltar_connection.session.token}'},
                                 json={'model_config': model_config})
        if response.status_code != 200:  # HTTP_200_OK
            raise RuntimeError(f"status_code was not 200. status_code={response.status_code}, text={response.text}")

        new_model_json = response.json()
        new_model_pk = new_model_json['id']
        new_model_url = f'{self.zoltar_connection.host}/api/model/{new_model_pk}'
        return Model(self.zoltar_connection, new_model_url, new_model_json)


class Model(ZoltarResource):
    """
    Represents a Zoltar forecast model, and is the entry point for getting its Forecasts as well as uploading them.
    """

    _repr_keys = ('name',)


    def __init__(self, zoltar_connection, uri, initial_json=None):
        super().__init__(zoltar_connection, uri, initial_json)


    @property
    def name(self):
        return self.json['name']


    @property
    def forecasts(self):
        """
        :return: a list of this Model's Forecasts
        """
        forecasts_json_list = self.zoltar_connection.json_for_uri(self.uri + 'forecasts/')
        return [Forecast(self.zoltar_connection, forecast_json['url'], forecast_json)
                for forecast_json in forecasts_json_list]


    def forecast_for_pk(self, forecast_pk):
        forecast_uri = self.zoltar_connection.host + f'/api/forecast/{forecast_pk}/'
        return Forecast(self.zoltar_connection, forecast_uri)


    def upload_forecast(self, forecast_json_fp, source, timezero_date, data_version_date=None):
        """Uploads a forecast file.

        :param forecast_json_fp: a JSON file in the "JSON IO dict" format accepted by
            utils.forecast.load_predictions_from_json_io_dict()
        :param timezero_date: YYYY-MM-DD DATE FORMAT
        :param data_version_date: YYYY-MM-DD DATE FORMAT
        :return: an UploadFileJob
        """
        data = {'timezero_date': timezero_date}
        if data_version_date:
            data['data_version_date'] = data_version_date
        response = requests.post(self.uri + 'forecasts/',
                                 headers={'Authorization': f'JWT {self.zoltar_connection.session.token}'},
                                 data=data,
                                 files={'data_file': (source, forecast_json_fp, 'application/json')})
        if response.status_code != 200:  # HTTP_200_OK
            raise RuntimeError(f"upload_forecast(): status code was not 200. status_code={response.status_code}. "
                               f"text={response.text}")

        upload_file_job_json = response.json()
        return UploadFileJob(self.zoltar_connection, upload_file_job_json['url'])


class Forecast(ZoltarResource):
    _repr_keys = ('source', 'created_at')


    def __init__(self, zoltar_connection, uri, initial_json=None):
        super().__init__(zoltar_connection, uri, initial_json)


    @property
    def timezero(self):
        return TimeZero(self.zoltar_connection, self.json['time_zero'])


    @property
    def source(self):
        return self.json['source']


    @property
    def created_at(self):
        return self.json['created_at']


    def data(self):
        """
        :return: this forecast's data as a dict in the "JSON IO dict" format accepted by
            utils.forecast.load_predictions_from_json_io_dict()
        """
        data_uri = self.json['forecast_data']
        response = requests.get(data_uri,
                                headers={'Authorization': 'JWT {}'.format(self.zoltar_connection.session.token)})
        if response.status_code != 200:  # HTTP_200_OK
            raise RuntimeError(f"data(): status code was not 200. status_code={response.status_code}. "
                               f"text={response.text}")

        return json.loads(response.content.decode('utf-8'))


class Unit(ZoltarResource):
    _repr_keys = ('name',)


    def __init__(self, zoltar_connection, uri, initial_json=None):
        super().__init__(zoltar_connection, uri, initial_json)


    @property
    def name(self):
        return self.json['name']


class Target(ZoltarResource):
    _repr_keys = ('name', 'type', 'is_step_ahead', 'step_ahead_increment', 'unit')


    def __init__(self, zoltar_connection, uri, initial_json=None):
        super().__init__(zoltar_connection, uri, initial_json)


    @property
    def name(self):
        return self.json['name']


    @property
    def type(self):
        return self.json['type']


    @property
    def is_step_ahead(self):
        return self.json['is_step_ahead']


    @property
    def step_ahead_increment(self):
        return self.json['step_ahead_increment']


    @property
    def unit(self):
        return self.json['unit']


class TimeZero(ZoltarResource):
    _repr_keys = ('timezero_date', 'data_version_date', 'is_season_start', 'season_name')


    def __init__(self, zoltar_connection, uri, initial_json=None):
        super().__init__(zoltar_connection, uri, initial_json)


    @property
    def timezero_date(self):
        return self.json['timezero_date']


    @property
    def data_version_date(self):
        return self.json['data_version_date']


    @property
    def is_season_start(self):
        return self.json['is_season_start']


    @property
    def season_name(self):
        return self.json['season_name']


class UploadFileJob(ZoltarResource):
    STATUS_ID_TO_STR = {
        0: 'PENDING',
        1: 'CLOUD_FILE_UPLOADED',
        2: 'QUEUED',
        3: 'CLOUD_FILE_DOWNLOADED',
        4: 'SUCCESS',
        5: 'FAILED',
    }


    def __init__(self, zoltar_connection, uri):
        super().__init__(zoltar_connection, uri)


    def __repr__(self):
        return str((self.__class__.__name__, self.uri, self.id, self.status_as_str)) if self._json \
            else super().__repr__()


    @property
    def output_json(self):
        return self.json['output_json']


    @property
    def status_as_str(self):
        status_int = self.json['status']
        return UploadFileJob.STATUS_ID_TO_STR[status_int]
