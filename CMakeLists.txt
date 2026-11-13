cmake_minimum_required(VERSION 3.18...4.4)

option(OCARINA_HOST_TOOLS "Build the desktop melody validator" OFF)

if(OCARINA_HOST_TOOLS)
  project(pico_ocarina VERSION 1.2.0 LANGUAGES CXX)
else()
  if(NOT PICO_SDK_PATH AND DEFINED ENV{PICO_SDK_PATH})
    set(PICO_SDK_PATH "$ENV{PICO_SDK_PATH}")
  endif()
  if(NOT EXISTS "${PICO_SDK_PATH}/external/pico_sdk_import.cmake")
    message(FATAL_ERROR "Set PICO_SDK_PATH to Pico SDK 2.1.1")
  endif()
  set(PICO_NO_PICOTOOL ON)
  include("${PICO_SDK_PATH}/external/pico_sdk_import.cmake")
  set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
  project(pico_ocarina VERSION 1.2.0 LANGUAGES C CXX ASM)
  set(CMAKE_C_STANDARD 11)
  add_compile_options("-ffile-prefix-map=${CMAKE_CURRENT_SOURCE_DIR}=."
                      "-ffile-prefix-map=${PICO_SDK_PATH}=pico-sdk")
  pico_sdk_init()
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_library(melody STATIC src/melody.cpp src/song_store.cpp src/upload_session.cpp)
target_include_directories(melody PUBLIC src)
target_compile_options(melody PRIVATE -Wall -Wextra)

if(OCARINA_HOST_TOOLS)
  add_executable(melody_check tools/melody_check.cpp)
  target_link_libraries(melody_check PRIVATE melody)
else()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  set(SONG_GENERATED_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
  add_custom_command(
    OUTPUT "${SONG_GENERATED_DIR}/song.h" "${SONG_GENERATED_DIR}/fallback_melody.h"
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_song.py"
            --output-dir "${SONG_GENERATED_DIR}"
    DEPENDS tools/generate_song.py tools/melody_format.py songs/auld_lang_syne_playback.json
    COMMENT "Generating default song data"
    VERBATIM)
  add_custom_target(song_data DEPENDS "${SONG_GENERATED_DIR}/song.h" "${SONG_GENERATED_DIR}/fallback_melody.h")
  add_executable(pico_ocarina src/main.cpp src/pro_controller.cpp src/usb_descriptors.cpp
                              src/pico_song_flash.cpp src/configuration.cpp)
  add_dependencies(pico_ocarina song_data)
  target_include_directories(pico_ocarina PRIVATE src "${SONG_GENERATED_DIR}")
  target_compile_options(pico_ocarina PRIVATE -Wall -Wextra)
  target_compile_definitions(pico_ocarina PRIVATE PICO_STACK_SIZE=4096)
  target_link_libraries(pico_ocarina melody pico_stdlib tinyusb_device tinyusb_board hardware_sync hardware_flash)
  target_link_options(pico_ocarina PRIVATE "LINKER:-T,${CMAKE_CURRENT_SOURCE_DIR}/src/song_partition.ld")
  set_property(TARGET pico_ocarina APPEND PROPERTY LINK_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/song_partition.ld")
  pico_enable_stdio_usb(pico_ocarina 0)
  pico_enable_stdio_uart(pico_ocarina 0)
  pico_set_program_name(pico_ocarina "Pico Ocarina")
  pico_set_program_version(pico_ocarina "${PROJECT_VERSION}")
  pico_set_program_url(pico_ocarina "https://github.com/Ting-777/Pico_Ocarina/tree/prod")
  pico_add_extra_outputs(pico_ocarina)
  add_custom_command(TARGET pico_ocarina POST_BUILD
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/bin_to_uf2.py"
            "${CMAKE_CURRENT_BINARY_DIR}/pico_ocarina.bin"
            "${CMAKE_CURRENT_BINARY_DIR}/pico_ocarina.uf2"
    COMMENT "Creating RP2040 UF2"
    VERBATIM)
  set_property(TARGET pico_ocarina APPEND PROPERTY LINK_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/tools/bin_to_uf2.py")
endif()
