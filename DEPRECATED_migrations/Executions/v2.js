const getItems = async (ddb, lastEvalKey) => {
    const {Items, LastEvaluatedKey} = await ddb.scan({
        TableName: 'Executions',
        ExclusiveStartKey: lastEvalKey,
    }).promise();
    return {Items: Items.filter(item => !item.asset_id && item.PK.includes("TENANT")), LastEvaluatedKey};
}

const transformUp = async (ddb, preparationData, isDryRun) => {
    let lastEvalKey = undefined;
    do {
        const {Items, LastEvaluatedKey} = await getItems(ddb, lastEvalKey)
        lastEvalKey = LastEvaluatedKey

        if (!isDryRun) {
            await remove(ddb, Items)
        } else {
            console.info(Items, 'Deleted items')
            console.info(Items.length, 'Deleted items amount')
        }
    } while (lastEvalKey)
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
    sequence: 2, // the migration number
}
