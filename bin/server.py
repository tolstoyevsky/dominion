#!/usr/bin/env python3
# Copyright 2016 Evgeny Golyshev. All Rights Reserved.
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
# limitations under the License.

import aioredis
import tornado.options
import tornado.web
import tornado.websocket
from shirow.ioloop import IOLoop
from shirow.server import RPCServer, TOKEN_PATTERN, remote
from tornado.options import options

from dominion.settings import REDIS_HOST, REDIS_PORT


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r'/dominion/token/' + TOKEN_PATTERN, Dominion),
        ]
        super().__init__(handlers)


class Dominion(RPCServer):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)

        self._subscriber = None

    def destroy(self):
        if self._subscriber:
            self._subscriber.close()

    @remote
    async def get_build_log(self, request, image_id):
        self._subscriber = await aioredis.create_redis((REDIS_HOST, int(REDIS_PORT)))
        res = await self._subscriber.subscribe(f'build-log-{image_id}')
        channel = res[0]

        request.ret_and_continue('The image will start being built in a few seconds...\r\n')
        while await channel.wait_message():
            msg = await channel.get()
            request.ret_and_continue(msg.decode('utf8'))


def main():
    tornado.options.parse_command_line()
    IOLoop().start(Application(), options.port)


if __name__ == "__main__":
    main()
