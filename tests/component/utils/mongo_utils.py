class WriteMock:
    def __init__(self):
        self.matched_count = 0
        self.modified_count = 0
        self.inserted_count = 0
        self.upserted_count = 0


class CollectionMock:
    def __init__(self):
        self.operations = []

    def bulk_write(self, write_operation):
        for update_item in write_operation:
            self.operations.append(update_item._doc)
        return WriteMock()
