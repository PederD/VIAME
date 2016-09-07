# vivia External Project
#
# Required symbols are:
#   VIAME_BUILD_PREFIX - where packages are built
#   VIAME_BUILD_INSTALL_PREFIX - directory install target
#   VIAME_PACKAGES_DIR - location of git submodule packages
#   VIAME_ARGS_COMMON -
##

set( VIAME_PROJECT_LIST ${VIAME_PROJECT_LIST} vivia )

if( WIN32 )
  set( VIAME_QMAKE_EXE ${VIAME_BUILD_INSTALL_PREFIX}/bin/qmake.exe )
else()
  set( VIAME_QMAKE_EXE ${VIAME_BUILD_INSTALL_PREFIX}/bin/qmake )
endif()

ExternalProject_Add(vivia
  DEPENDS fletch vibrant
  PREFIX ${VIAME_BUILD_PREFIX}
  SOURCE_DIR ${VIAME_PACKAGES_DIR}/vivia
  CMAKE_GENERATOR ${gen}
  CMAKE_ARGS
    ${VIAME_ARGS_COMMON}
    ${VIAME_ARGS_fletch}
    ${VIAME_ARGS_libkml}

    # Required
    -DVISGUI_ENABLE_VIDTK:BOOL=OFF
    -DVISGUI_ENABLE_VIQUI:BOOL=OFF
    -DVISGUI_ENABLE_VSPLAY:BOOL=ON
    -DVISGUI_ENABLE_VPVIEW:BOOL=ON

    -DLIBJSON_INCLUDE_DIR:PATH=${VIAME_BUILD_INSTALL_PREFIX}/include/json
    -DQT_QMAKE_EXECUTABLE:PATH=${VIAME_QMAKE_EXE}

  INSTALL_DIR ${VIAME_BUILD_INSTALL_PREFIX}
  )

ExternalProject_Add_Step(vivia forcebuild
  COMMAND ${CMAKE_COMMAND}
    -E remove ${VIAME_BUILD_PREFIX}/src/vivia-stamp/vivia-build
  COMMENT "Removing build stamp file for build update (forcebuild)."
  DEPENDEES configure
  DEPENDERS build
  ALWAYS 1
  )

set(VIAME_ARGS_vivia
  -Dvivia_DIR:PATH=${VIAME_BUILD_PREFIX}/src/vivia-build
  )
