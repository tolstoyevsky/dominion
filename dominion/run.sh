cd ${RPI2_BUILDER_LOCATION}
./rpi23-gen-image.sh

cd ${WORKSPACE_DIR}
tar czf ${BUILD_ID}.tar.gz ${BUILD_ID}.img ${BUILD_ID}.bmap
rm ${BUILD_ID}.bmap
rm ${BUILD_ID}.img
