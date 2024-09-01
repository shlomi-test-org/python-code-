const up = (item) => {
    jit_event_name = item.event_type;
    delete item.event_type;
    return {
        ...item,
        jit_event_name
    }
}

const getItems = async (ddb, lastEvalKey) => {
    const {Items, LastEvaluatedKey} = await ddb.scan({
        TableName: 'Executions',
        ExclusiveStartKey: lastEvalKey,
    }).promise();
    return {Items: Items.filter(item => item.event_type && !item.jit_event_name), LastEvaluatedKey};
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
            console.info(updatedItems, 'updatedItems')
            console.info(updatedItems.length, 'updatedItems.length')
        }
    } while (lastEvalKey)
}

const save = async (ddb, items) => {
    return await Promise.all(items.map((item) =>
        ddb.put({
            TableName: 'Executions',
            Item: item,
        }).promise()
    ))
}


module.exports = {
    transformUp,
    // transformDown,
    // prepare, // pass this function only if you need preparation data for the migration
    sequence: 1, // the migration number
}
