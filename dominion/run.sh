#!/bin/sh

set -e

cd ${PIEMAN_PATH}
./pieman.sh
mv build/${PROJECT_NAME}/${PROJECT_NAME}.img.gz ${WORKSPACE}
rm -r build/${PROJECT_NAME}
