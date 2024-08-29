const up = (item) => (
    {
        ...item,
        max_resources_in_use: 10,
    }
);

const getItems = async (ddb, lastEvalKey) => {
    const {Items, LastEvaluatedKey} = await ddb.scan({
        TableName: 'Resources',
        ExclusiveStartKey: lastEvalKey,
    }).promise();
    return {Items: Items.filter(item => item.PK.includes("TENANT#")), LastEvaluatedKey};
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
            await save(ddb, updatedItems)
        } else {
            console.info(updatedItems, 'Updated Items')
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


module.exports = {
    transformUp,
    // transformDown,
    // prepare, // pass this function only if you need preparation data for the migration
    sequence: 3, // the migration number
}
