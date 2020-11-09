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
from celery import Task
from celery.utils.log import get_task_logger

from images.models import Image

DOCKER_CLIENT = docker.from_env()

LOGGER = get_task_logger(__name__)


class BaseBuildTask(Task):
    """Base class for the build task.
    The primary goal of the class is to make it possible to maintain the 'success' and 'failure'
    handlers outside of the build task.
    """

    def _finish(self, status, **kwargs):
        container = kwargs['container']
        image_id = kwargs['image_id']

        image = Image.objects.get(image_id=image_id)
        image.change_status_to(status)
        image.set_finished_at()
        image.store_build_log(container.logs())

        self._remove_container(container)

    @staticmethod
    def _remove_container(container):
        container.remove()

    def on_success(self, retval, task_id, args, kwargs):
        """Invoked when a task succeeds. """

        self._finish(Image.SUCCEEDED, **kwargs)

        LOGGER.info(f'{kwargs["image_id"]} succeeded')

    def on_failure(self, exc, task_id, args, kwargs, _info):
        """Invoked when task fails. """

        self._finish(Image.FAILED, **kwargs)

        LOGGER.info(f'{kwargs["image_id"]} failed')
