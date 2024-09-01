const up = (item) => {
    return {
        ...item,
        SK: `RUNNER#github_actions`,
        runner: 'github_actions',
    }
}

const getItems = async (ddb, lastEvalKey) => {
    const {Items, LastEvaluatedKey} = await ddb.scan({
        TableName: 'Resources',
        ExclusiveStartKey: lastEvalKey,
    }).promise();
    return {Items: Items.filter(item => item.SK === 'RUNNER#github-actions'), LastEvaluatedKey};
}

const transformUp = async (ddb, preparationData, isDryRun) => {
    let lastEvalKey = undefined;
    do {
        const {Items, LastEvaluatedKey} = await getItems(ddb, lastEvalKey)
        lastEvalKey = LastEvaluatedKey

        const updatedItems = Items.map((item) => {
            return up(item)
        })

        if (!isDryRun) {
            await remove(ddb, Items)
            await save(ddb, updatedItems)
        } else {
            console.info(Items, 'Removed items')
            console.info(updatedItems, 'Created Items')
            console.info(updatedItems.length, 'updatedItems.length')
        }
    } while (lastEvalKey)
}

const save = async (ddb, items) => {
    return await Promise.all(items.map((item) =>
        ddb.put({
            TableName: 'Resources',
            Item: item,
        }).promise()
    ))
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
    sequence: 2, // the migration number
}
