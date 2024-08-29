def pop_all_indexes(record: dict):
    record_copy = record.copy()
    indexes = ['PK', 'SK', 'GSI1PK', 'GSI1SK', 'GSI2PK', 'GSI2SK', 'GSI3PK', 'GSI3SK', 'GSI4PK', 'GSI4SK', 'GSI5PK',
               'GSI5SK', 'GSI6PK', 'GSI6SK', 'GSI7PK', 'GSI7SK', 'GSI8PK', 'GSI8SK', 'GSI9PK', 'GSI9SK', 'LSI1SK']
    for index in indexes:
        record_copy.pop(index, None)

    return record_copy
