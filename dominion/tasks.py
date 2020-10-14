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

from dominion.app import APP


class BaseBuildTask(Task):
    """Base class for the build task.
    The primary goal of the class is to make it possible to maintain the 'success' and 'failure'
    handlers outside of the build task.
    """

    def on_success(self, retval, task_id, args, kwargs):
        """Invoked when a task succeeds. """

        print('Success')

    def on_failure(self, exc, task_id, args, kwargs, _info):
        """Invoked when task fails. """

        print('Fail')


@APP.task(bind=True, base=BaseBuildTask)
def build(_self):
    """Builds an image. """

    print('Stub')
