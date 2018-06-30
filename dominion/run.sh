#!/bin/sh

set -e

cd ${PIEMAN_PATH}
./pieman.sh
mv build/${PROJECT_NAME}.img.gz ${WORKSPACE}
