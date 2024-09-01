/*
    This migration will delete all the in use resources and reset the resources in use item
 */


const getRunnerItems = async (ddb) => {
    let items = [];
    let lastEvalKey;
    do {
        const {Items, LastEvaluatedKey} = await ddb.scan({
            TableName: 'Resources',
            ExclusiveStartKey: lastEvalKey,
            FilterExpression: 'begins_with(#SK, :SK_PREFIX) AND #RESOURCES_IN_USE > :MIN_RESOURCES_IN_USE',
            ExpressionAttributeNames: {
                '#SK': 'SK',
                '#RESOURCES_IN_USE': 'resources_in_use'
            },
            ExpressionAttributeValues: {
                ':SK_PREFIX': 'RUNNER',
                ':MIN_RESOURCES_IN_USE': 0
            },
        }).promise();
        items = items.concat(Items);
        lastEvalKey = LastEvaluatedKey;
    } while (lastEvalKey)
    return items;
}

const getJitEventsItems = async (ddb) => {
    let items = [];
    let lastEvalKey;
    do {
        const {Items, LastEvaluatedKey} = await ddb.scan({
            TableName: 'Resources',
            ExclusiveStartKey: lastEvalKey,
            FilterExpression: 'begins_with(#SK, :SK_PREFIX)',
            ExpressionAttributeNames: {
                '#SK': 'SK',
            },
            ExpressionAttributeValues: {
                ':SK_PREFIX': 'JIT_EVENT_ID',
            },
        }).promise();
        items = items.concat(Items);
        lastEvalKey = LastEvaluatedKey;
    } while (lastEvalKey)
    return items;
}

const transformUp = async (ddb, preparationData, isDryRun) => {
    const jitEventsItems = await getJitEventsItems(ddb);
    const runnerItems = await getRunnerItems(ddb);
    const updatedRunnerItems = runnerItems.map((item) => {
        return up(item)
    })

    if (!isDryRun) {
        console.info(`removing ${jitEventsItems.length} jit events`)
        await remove(ddb, jitEventsItems);
    } else {
        console.info(`DRY RUN - removing ${jitEventsItems.length} jit events`)
        console.log('DRY RUN - JIT Events: ', jitEventsItems);
    }
    if (!isDryRun) {
        console.info(`updating ${updatedRunnerItems.length} runner items`)
        await save(ddb, updatedRunnerItems);
    } else {
        console.info(`DRY RUN - updating ${updatedRunnerItems.length} runner items`)
        console.log('DRY RUN - Runner Items: ', updatedRunnerItems);
    }
}

const up = (item) => {
    return {
        ...item,
        resources_in_use: 0
    }
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
    sequence: 5, // the migration number
}
