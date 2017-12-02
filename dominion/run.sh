#!/bin/sh

set -e

cd ${PIEMAN_PATH}
./pieman.sh
mv build/${PROJECT_NAME}/${PROJECT_NAME}.img ${WORKSPACE}
gzip ${WORKSPACE}/${PROJECT_NAME}.img
rm -r build/${PROJECT_NAME}
