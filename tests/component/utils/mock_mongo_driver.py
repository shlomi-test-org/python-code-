import os

import mongomock
from jit_utils.models.findings.entities import FindingSpecs

from tests.component.utils.mock_get_ssm_param import mock_get_ssm_param


def mock_mongo_driver(mocker):
    os.environ["DB_NAME"] = "DB_NAME"
    os.environ["FINDINGS_COLLECTION_NAME"] = "findings"
    os.environ["IGNORE_RULES_COLLECTION_NAME"] = "ignore_rules"
    mock_get_ssm_param(mocker)

    mock_mongo_client = mongomock.MongoClient()
    db = mock_mongo_client["DB_NAME"]

    # Patch the `get_mongo_client` function to return the mock mongo client
    mocker.patch("src.lib.data.mongo.mongo_driver.get_mongo_client", return_value=mock_mongo_client)

    # This is done due to mongomock limitations, as it does not support array filters
    # https://app.shortcut.com/jit/story/24244/finding-service-replace-mongomock-due-to-unsupported-features-and-lack-of-maintenance

    # Save the reference to the original update_many method
    original_update_many = db.findings.update_many

    def custom_update_many(filter, update, upsert=False, array_filters=None):
        # Exclude the 'specs.$[element].v' part from the update operation
        if array_filters:
            value = update['$set'].pop('specs.$[element].v')
            # If '$set' is now empty, remove it as well
            if not update['$set']:
                del update['$set']
            # If there are array filters, we need to update the 'specs' element
            key = array_filters[0].get('element.k')
            key_index = list(FindingSpecs.__fields__.keys()).index(key)
            # add this to the update expression
            update['$set'][f'specs.{key_index}.v'] = value
        # Call the original update_many method without the specs element and array_filters
        return original_update_many(filter, update, upsert=upsert)

    # Now, patch `update_many` with `custom_update_many`, without losing the reference to the original method
    mocker.patch.object(db.findings, 'update_many',
                        new=custom_update_many)
    return db
