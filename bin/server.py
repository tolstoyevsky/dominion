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

import os
import pty
import signal
from pathlib import Path

import tornado.options
import tornado.web
import tornado.websocket
from shirow.ioloop import IOLoop
from shirow.server import RPCServer, TOKEN_PATTERN, remote
from tornado.options import define, options

define('build_log_dir', help='The path to the directory which contains build logs',
       default='/tmp/dominion')

BUF_SIZE = 65536


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r'/dominion/token/' + TOKEN_PATTERN, Dominion),
        ]
        super().__init__(handlers)


class Dominion(RPCServer):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)

        self._fd = None
        self._pid = None

    def destroy(self):
        if self._fd:
            self.io_loop.remove_handler(self._fd)

        if self._pid:
            os.kill(self._pid, signal.SIGKILL)  # kill zombie process

    @remote
    async def get_rt_build_log(self, request, build_id):
        build_log = os.path.join(options.build_log_dir, '{}.log'.format(build_id))
        Path(build_log).touch()

        self._pid, self._fd = pty.fork()
        if self._pid == 0:  # child
            command_line = ['echo', 'Hello, World!', ]
            os.execvp(command_line[0], command_line)
        else:  # parent
            def build_log_handler(*_args, **_kwargs):
                try:
                    data = os.read(self._fd, BUF_SIZE)
                except OSError:
                    return

                request.ret_and_continue(data.decode('utf8'))

            self.io_loop.add_handler(self._fd, build_log_handler, self.io_loop.READ)

            # The parent process finishes not waiting for the child.
            # The child process becomes a zombie.


def main():
    tornado.options.parse_command_line()
    IOLoop().start(Application(), options.port)

if __name__ == "__main__":
    main()
