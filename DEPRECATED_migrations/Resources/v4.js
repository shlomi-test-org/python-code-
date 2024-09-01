const getTenants = async (ddb) => {
    let lastEvalKey;
    let tenants = []
    do {
        const {Items, LastEvaluatedKey} = await ddb.scan({
            TableName: 'Tenants',
            ExclusiveStartKey: lastEvalKey,
            FilterExpression: '#is_active = :is_active AND begins_with(#PK, :PK_prefix) AND begins_with(#SK, :SK_prefix)',
            ExpressionAttributeNames: {
                '#is_active': 'is_active',
                '#PK': 'PK',
                '#SK': 'SK',
            },
            ExpressionAttributeValues: {
                ':is_active': true,
                ':PK_prefix': 'TENANT',
                ':SK_prefix': 'TENANT',
            },
        }).promise();
        tenants = [...tenants, ...Items]
        lastEvalKey = LastEvaluatedKey;
    } while (lastEvalKey)
    return tenants.map(tenant => (tenant.tenant_id))
}

const getItems = async (ddb, lastEvalKey) => {
    const {Items, LastEvaluatedKey} = await ddb.scan({
        TableName: 'Resources',
        ExclusiveStartKey: lastEvalKey,
        FilterExpression: 'begins_with(#PK, :PK_prefix) AND begins_with(#SK, :SK_prefix)',
        ExpressionAttributeNames: {
            '#PK': 'PK',
            '#SK': 'SK',
        },
        ExpressionAttributeValues: {
            ':PK_prefix': 'TENANT',
            ':SK_prefix': 'RUNNER',
        },
    }).promise();
    return {Items, LastEvaluatedKey};
}

const transformUp = async (ddb, preparationData, isDryRun) => {
    let lastEvalKey;
    const tenant_ids = await getTenants(ddb);
    do {
        const {Items, LastEvaluatedKey} = await getItems(ddb, lastEvalKey)
        lastEvalKey = LastEvaluatedKey

        const resourceToDelete = Items.filter(item => (
            !tenant_ids.includes(item.tenant_id)
        ))

        if (!isDryRun) {
            await remove(ddb, resourceToDelete)
        } else {
            console.info(resourceToDelete, 'deleted Items')
            console.info(resourceToDelete.length, 'resourceToDelete.length')
        }
    } while (lastEvalKey)
}

const remove = async (ddb, items) => {
    return await Promise.all(items.map((item) =>
        ddb.delete({
            TableName: 'Resources',
            Key: {
                PK: item.PK,
                SK: item.SK,
            },
        }).promise()
    ))
}


module.exports = {
    transformUp,
    // transformDown,
    // prepare, // pass this function only if you need preparation data for the migration
    sequence: 4, // the migration number
}
