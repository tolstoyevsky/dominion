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

from celery import Task
from celery.utils.log import get_task_logger

from images.models import Image

from dominion import tasks
from dominion.exceptions import Interrupted
from dominion.settings import QUEUE_EMAIL_NAME

LOGGER = get_task_logger(__name__)


class BaseBuildTask(Task):
    """Base class for the build task.
    The primary goal of the class is to make it possible to maintain the 'success' and 'failure'
    handlers outside of the build task.
    """

    def _email(self, image_id, status):
        email_kwargs = {
            'queue': QUEUE_EMAIL_NAME,
            'retry': True,
            'retry_policy': {
                'max_retries': 6,
                'interval_max': 10,
            },
        }
        tasks.email.apply_async((image_id, status, ), **email_kwargs)

    def _finish(self, status, **kwargs):
        pieman = kwargs['pieman']
        image_id = kwargs['image_id']

        image = Image.objects.get(image_id=image_id)
        image.change_status_to(status)
        image.set_finished_at()
        image.store_build_log(pieman.logs())

        pieman.remove()

        self._email(image_id, status)

    def on_success(self, retval, task_id, args, kwargs):
        """Invoked when a task succeeds. """

        self._finish(Image.SUCCEEDED, **kwargs)

        LOGGER.info(f'{kwargs["image_id"]} succeeded')

    def on_failure(self, exc, task_id, args, kwargs, _info):
        """Invoked when task fails or is interrupted by the 'watch' task. """

        if isinstance(exc, Interrupted):
            self._finish(Image.INTERRUPTED, **kwargs)
            LOGGER.info(f'{kwargs["image_id"]} interrupted')
        else:
            self._finish(Image.FAILED, **kwargs)
            LOGGER.info(f'{kwargs["image_id"]} failed')
