# Copyright 2020 Evgeny Golyshev. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License

import docker
from docker.errors import APIError, NotFound

from dominion import settings
from dominion.exceptions import DoesNotExist, Failed, Interrupted

_DOCKER_CLIENT = docker.from_env()

DOCKER = _DOCKER_CLIENT.containers

EXIT_STATUS = 'exited'


class PiemanDocker:
    def __init__(self, container_name, *, must_exist=False):
        self._container_name = container_name
        self._container = None

        try:
            self._container = DOCKER.get(container_name)
        except NotFound:
            if must_exist:
                raise DoesNotExist

        self._run_kwargs = {
            'detach': True,
            'name': container_name,
            'privileged': True,
            'volumes': {
                '/dev': {'bind':'/dev', 'mode': 'rw'},
                settings.BUILD_RESULT_PATH: {'bind':'/result', 'mode': 'rw'},
            },
            'environment': {
                'TERM': 'xterm',
            },
        }

    @staticmethod
    def _terminalize(line):
        return line.decode('utf-8').replace('\n', '\r\n')

    def _iter_logs(self):
        for line in self._container.logs(follow=True, stream=True):
            yield self._terminalize(line)

    def get_status(self):
        """Gets the status of the Pieman container. If the container does not exist, The method
        raises ``DoesNotExist``.
        """

        try:
            self._container.reload()
        except NotFound:
            raise DoesNotExist

        return self._container.status

    def kill(self):
        """Kills the Pieman container. The method does not raise any exception if the container
        either does not exist or is not running.
        """

        try:
            self._container.kill()
        except NotFound:
            raise DoesNotExist
        except APIError:
            """Probably the container is not running. Simply ignore it. """

    def logs(self, stream=False):
        """Gets logs from the Pieman container.

        The ``stream`` parameter makes the ``logs`` method return a blocking generator you can
        iterate over to retrieve log output as it happens.
        """

        return self._iter_logs() if stream else self._container.logs()

    def remove(self):
        """Removes the Pieman container. The method does not raise any exception if the container
        does not exist.
        """

        try:
            self._container.remove()
        except NotFound:
            """There is nothing to do in this case. """

    def run(self, env=None):
        """Runs the Pieman container, optionally passing environment variables to it
        via ```env``.
        """

        if env:
            self._run_kwargs['environment'].update(env)

        self._container = DOCKER.run('cusdeb/pieman', **self._run_kwargs)

    def wait(self):
        """Blocks until the Pieman container stops, then check its exit code.
        The method raises
        * ``Interrupted`` if the code is 137.
        * ``Failed`` if the code is greater than 0.
        """

        self._container.reload()
        exit_code = self._container.wait()

        if exit_code['StatusCode'] == 137:
            raise Interrupted

        if exit_code['StatusCode'] > 0:
            raise Failed
