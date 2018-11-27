#!/bin/sh

set -e

cd ${PIEMAN_PATH}
./pieman.sh

if [ -z ${CREATE_ONLY_MENDER_ARTIFACT+x} ]; then
    CREATE_ONLY_MENDER_ARTIFACT=false
fi

if ${CREATE_ONLY_MENDER_ARTIFACT}; then
    mv build/${PROJECT_NAME}.mender ${WORKSPACE}
else
    mv build/${PROJECT_NAME}.img.gz ${WORKSPACE}
fi
