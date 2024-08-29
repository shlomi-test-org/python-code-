import json
import responses
from typing import Optional
from mongomock import MongoClient


class MongoDataApiMock:
    def __init__(self,
                 base_url: str,
                 mongo_client: Optional[MongoClient] = None,
                 **callback_overrides):
        self.base_url = base_url
        # in order to override callback functions we're allowing to init the Mongo client outside the class
        mongo_client = mongo_client if mongo_client else MongoClient()
        self.db = mongo_client.test

        # mock requests
        self.mock_find_request(callback_overrides.get('find_override'))
        self.mock_find_one_request(callback_overrides.get('find_one_override'))
        self.mock_count_request(callback_overrides.get('count_override'))
        self.mock_insert_one_request(callback_overrides.get('insert_one_override'))
        self.mock_update_many_request(callback_overrides.get('update_many_override'))
        self.mock_delete_one_request(callback_overrides.get('delete_one_override'))

    def mock_find_request(self, callback_override):
        def find_callback(request):
            body = json.loads(request.body)
            filter_expression = body.get("filter")
            sort = body.get("sort")
            limit = body.get("limit")
            findings = []
            collection = self.db[body['collection']]

            for finding in collection.find(filter=filter_expression,
                                           limit=limit, sort=sort.items()):
                findings.append(finding)

            return 200, {}, json.dumps({"documents": findings})

        responses.add_callback(responses.POST,
                               f'{self.base_url}/action/find',
                               callback=callback_override if callback_override else find_callback,
                               content_type='application/json')

    def mock_find_one_request(self, callback_override):
        def find_callback(request):
            body = json.loads(request.body)
            filter_expression = body.get("filter")
            collection = self.db[body['collection']]

            finding = collection.find_one(filter=filter_expression)

            return 200, {}, json.dumps({"document": finding})

        responses.add_callback(responses.POST,
                               f'{self.base_url}/action/findOne',
                               callback=callback_override if callback_override else find_callback,
                               content_type='application/json')

    def mock_delete_one_request(self, callback_override):
        def delete_callback(request):
            body = json.loads(request.body)
            filter_expression = body.get("filter")
            collection = self.db[body['collection']]

            result = collection.delete_one(filter=filter_expression)

            return 200, {}, json.dumps({"deleted_count": result.deleted_count, "acknowledged": result.acknowledged})

        responses.add_callback(responses.POST,
                               f'{self.base_url}/action/deleteOne',
                               callback=callback_override if callback_override else delete_callback,
                               content_type='application/json')

    def mock_count_request(self, callback_override):
        def count_callback(request):
            body = json.loads(request.body)
            pipeline = body.get("pipeline")
            result = []

            collection = self.db[body['collection']]

            for finding in collection.aggregate(pipeline):
                result.append(finding)

            return 200, {}, json.dumps({"documents": result})

        responses.add_callback(responses.POST,
                               f'{self.base_url}/action/aggregate',
                               callback=callback_override if callback_override else count_callback)

    def mock_insert_one_request(self, callback_override):
        def insert_one_callback(request):
            body = json.loads(request.body)
            document = body.get("document")

            collection = self.db[body['collection']]

            collection.insert_one(document)

            return 201, {}, json.dumps({"document": "inserted"})

        responses.add_callback(responses.POST,
                               f'{self.base_url}/action/insertOne',
                               callback=callback_override if callback_override else insert_one_callback,
                               content_type='application/json'
                               )

    def mock_update_many_request(self, callback_override):
        def update_many_callback(request):
            body = json.loads(request.body)
            filter_expression = body.get("filter")
            update = body.get("update")
            collection = self.db[body['collection']]

            collection.update_many(filter=filter_expression, update=update)

            return 200, {}, json.dumps({"document": "updated"})

        responses.add_callback(responses.POST,
                               f'{self.base_url}/action/updateMany',
                               callback=callback_override if callback_override else update_many_callback,
                               content_type='application/json'
                               )
