/*
 * Copyright 2016 Maxim Karpinskiy, Evgeny Golyshev. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

import RPCClient from 'shirow/client/client.js';

var client = new RPCClient('ws://localhost:8888/dominion/token/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpcCI6IjEyNy4wLjAuMSIsInVzZXJfaWQiOjF9.kYIAQYDjOiZpjExvXZaAgemi4xiisvPEzvXEemmAJLY');

client.on('ready', function() {
    client.emitForce('get_rt_build_log').then(data => {
        console.log(data);
    });
});