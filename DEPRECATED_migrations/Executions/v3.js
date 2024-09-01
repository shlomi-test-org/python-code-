const getItems = async (ddb, lastEvalKey, creationTimeLimit) => {
    const {Items, LastEvaluatedKey} = await ddb.scan({
        TableName: 'Executions',
        ExclusiveStartKey: lastEvalKey,
        FilterExpression: '#created_at < :creation_time_limit AND not (#status in (:status_completed, :status_failed)) AND' +
            ' begins_with(#PK, :PK_prefix)',
        ExpressionAttributeNames: {
            '#created_at': 'created_at',
            '#status': 'status',
            '#PK': 'PK'
        },
        ExpressionAttributeValues: {
            ':creation_time_limit': creationTimeLimit,
            ':status_completed': 'completed',
            ':status_failed': 'failed',
            ':PK_prefix': 'TENANT'
        }
    }).promise();
    return {Items, LastEvaluatedKey};
}

const transformUp = async (ddb, preparationData, isDryRun) => {
    let lastEvalKey = undefined;
    let creationTimeLimit = new Date();
    creationTimeLimit.setMinutes(creationTimeLimit.getMinutes() - 15);
    creationTimeLimit = creationTimeLimit.toISOString();
    let deletedExecutions = 0;

    do {
        const {Items, LastEvaluatedKey} = await getItems(ddb, lastEvalKey, creationTimeLimit)
        lastEvalKey = LastEvaluatedKey

        if (!isDryRun) {
            await remove(ddb, Items)
        }
        deletedExecutions += Items.length
    } while (lastEvalKey)
    console.log(`Deleted ${deletedExecutions} executions`)
}

const remove = async (ddb, items) => {
    return await Promise.all(items.map((item) =>
        ddb.delete({
            TableName: 'Executions',
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
    sequence: 3, // the migration number
}
