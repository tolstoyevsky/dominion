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

import time

from celery.utils.log import get_task_logger
from docker.errors import APIError, NotFound
from dominion.app import APP
from dominion.base import DOCKER, BaseBuildTask
from dominion.settings import (
    CHANNEL_NAME,
    CONTAINER_NAME,
    POLLING_FREQUENCY,
    QUEUE_BUILD_NAME,
    QUEUE_WATCH_NAME,
    TIMEOUT,
)
from images.models import Image

from dominion.util import check_exit_code, connect_to_redis, terminalize

ENV = {
    'CR': 'false',
    'N': 30,
    'TERM': 'xterm',
}

EXIT_STATUS = 'exited'

LOGGER = get_task_logger(__name__)


@APP.task(bind=True, base=BaseBuildTask)
def build(self, image_id):
    """Builds an image. """

    container_name = CONTAINER_NAME.format(image_id=image_id)
    LOGGER.info(f'Running {container_name}')

    self.request.kwargs['image_id'] = image_id

    env = ENV.copy()

    run_kwargs = {
        'detach': True,
        'name': container_name,
        'environment': env,
    }
    container = self.request.kwargs['container'] = DOCKER.run('count-von-count', **run_kwargs)

    watch.apply_async((image_id, ), queue=QUEUE_WATCH_NAME)

    channel_name = CHANNEL_NAME.format(image_id=image_id)
    conn = connect_to_redis()
    for line in container.logs(follow=True, stream=True):
        conn.publish(channel_name, terminalize(line))

    container.reload()
    exit_code = container.wait()
    check_exit_code(exit_code['StatusCode'])


@APP.task
def spawn_builds():
    """Spawns the 'build' tasks. """

    image = Image.objects.get_any()
    if image:
        image.set_started_at()
        build.apply_async((image.image_id, ), queue=QUEUE_BUILD_NAME)


@APP.task
def watch(image_id):
    """Watches the corresponding Pieman container associated with an image id. The primary goal of
    the task is to kill the container if it exceeds its time limit specified via TIMEOUT.
    """

    container_name = CONTAINER_NAME.format(image_id=image_id)
    LOGGER.info(f'Watching {container_name}')

    try:
        container = DOCKER.get(container_name)
    except NotFound:
        LOGGER.info(f'{container_name} does not exist, so finishing the task')
        return

    retries_number = TIMEOUT // POLLING_FREQUENCY
    for _ in range(retries_number):
        try:
            container.reload()
            status = container.status
        except NotFound:
            status = EXIT_STATUS

        if status == EXIT_STATUS:
            LOGGER.info(f'{container_name} finished in time')
            break

        time.sleep(POLLING_FREQUENCY)
    else:
        try:
            LOGGER.info(f'Killing {container_name} because it exceeded its time limit.')
            container.kill()
        except APIError:  # in case the container stopped between the check and 'kill'
            "There is nothing to do in this case. "
