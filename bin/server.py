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
import socket

import tornado.options
import tornado.web
import tornado.websocket
from shirow.ioloop import IOLoop
from shirow.server import RPCServer, TOKEN_PATTERN, remote
from tornado import gen
from tornado.options import options

import dominion.util
from dominion.tasks import MAGIC_PHRASE


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r'/dominion/token/' + TOKEN_PATTERN, Dominion),
        ]
        tornado.web.Application.__init__(self, handlers)


class Dominion(RPCServer):
    def __init__(self, application, request, **kwargs):
        RPCServer.__init__(self, application, request, **kwargs)

        self._attempts_number = 30
        self._fd_added = False  # to prevent adding fd twice
        self._ptyfd = None
        self._return = False
        self._sock = None

    @remote
    def get_rt_build_log(self, request, build_id):
        socket_name = '/tmp/' + build_id

        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(socket_name)
        self._sock.listen(1)

        def request_handler(*args, **kwargs):
            sock, addr = self._sock.accept()
            (message, [fd, ]) = dominion.util.recv_fds(sock)
            self._ptyfd = fd

            # Cleaning up
            self.io_loop.remove_handler(self._sock.fileno())
            self._sock.close()

        self.io_loop.add_handler(self._sock.fileno(), request_handler,
                                 self.io_loop.READ)

        def build_log_handler(*args, **kwargs):
            try:
                data = os.read(self._ptyfd, 65536)
            except OSError:
                return

            if data != MAGIC_PHRASE:
                request.ret_and_continue(data.decode('utf8'))
            else:  # cleaning up
                self.io_loop.remove_handler(self._ptyfd)
                self._ptyfd = None
                self._return = True

        for i in range(self._attempts_number):
            if self._ptyfd and not self._fd_added:
                fd = os.fdopen(self._ptyfd)
                self.io_loop.add_handler(fd, build_log_handler,
                                         self.io_loop.READ)
                self._fd_added = True
                break

            self.logger.debug('An fd has not been received yet')
            yield gen.sleep(1)

        if not self._ptyfd:
            error_message = 'An fd has not been received'
            request.ret_error(error_message)
            self.logger.error(error_message)

        while True:  # do not allow get_rt_build_log to return
            if self._return:
                # request.ret cannot be called from build_log_handler. It must
                # be called from get_rt_build_log.
                request.ret(MAGIC_PHRASE.decode('utf8'))
                break
            else:
                yield gen.sleep(1)


def main():
    tornado.options.parse_command_line()
    IOLoop().start(Application(), options.port)

if __name__ == "__main__":
    main()
