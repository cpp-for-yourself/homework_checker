add_subdirectory(${PROJECT_SOURCE_DIR}/external/googletest
                 ${PROJECT_BINARY_DIR}/googletest)
include(CTest) # Include testing cmake package.

add_executable(my_tests test_dummy.cpp)
target_link_libraries(my_tests GTest::gtest_main)

add_test(my_tests ${PROJECT_BINARY_DIR}/tests/my_tests)
