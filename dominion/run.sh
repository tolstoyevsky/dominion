#!/bin/sh

set -e

cd ${PIEMAN_PATH}
./pieman.sh
mv build/${PROJECT_NAME}/${PROJECT_NAME}.img ${WORKSPACE}
rm -r build/${PROJECT_NAME}
cd ${WORKSPACE}
tar czf ${PROJECT_NAME}.tar.gz ${PROJECT_NAME}.img
rm ${PROJECT_NAME}.img
