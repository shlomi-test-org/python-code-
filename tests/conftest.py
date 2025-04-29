# Defining 'pytest_plugins' in a non-top-level conftest is no longer supported:
# It affects the entire test suite instead of just below the conftest as expected.
pytest_plugins = [
    'test_utils.controls.local_output_file_test_setup',
]
