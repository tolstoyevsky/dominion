# Copyright 2020 Denis Gavrilyuk. All Rights Reserved.
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

from django.conf import settings
from rocketchat.api import RocketChatAPI


class Chat:
    api = None

    def __init__(self, channel):
        Chat.api = Chat.api or RocketChatAPI(settings={'username': settings.ROCKET_CHAT_USERNAME,
                                                       'password': settings.ROCKET_CHAT_PASSWORD,
                                                       'domain': settings.ROCKET_CHAT_DOMAIN})
        self._channel = channel

    def contact_us(self, name, email, message):
        Chat.api.send_message(f'Новое сообщение от {name} \<{email}\>: {message}', self._channel)
