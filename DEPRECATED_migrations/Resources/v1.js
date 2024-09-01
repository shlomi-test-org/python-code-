const getPreparationsData = async (ddb, lastEvalKey) => {
    const {Items, LastEvaluatedKey} = await ddb.scan({
        TableName: 'Tenants',
        ExclusiveStartKey: lastEvalKey,
    }).promise();
    const relevant_items = Items.filter(item => item.PK.includes("TENANT") && item.SK.includes("TENANT") && item.PK === item.SK)
    return {
        Items: relevant_items.map(item => (item.tenant_id)),
        LastEvaluatedKey
    };
}

// The version of nodejs in the CI is 10.x which doesn't support .flat()
const flatArray = (arr) => {
  return arr.reduce((flat, toFlatten) => {
    return flat.concat(Array.isArray(toFlatten) ? flatArray(toFlatten) : toFlatten);
  }, []);
}

const prepare = async (ddb) => {
    let lastEvalKey
    let preparationData = []

    do {
        const {Items, LastEvaluatedKey} = await getPreparationsData(ddb, lastEvalKey)
        preparationData = preparationData.concat(Items)
        lastEvalKey = LastEvaluatedKey
    } while (lastEvalKey)

    return preparationData
}

const up = (tenant_id) => {
    const runners = ['github_actions', 'jit']
    return runners.map(runner => ({
            PK: `TENANT#${tenant_id}`,
            SK: `RUNNER#${runner}`,
            tenant_id,
            runner,
            resources_in_use: 0,
            max_resources_in_use: 20,
        })
    )
}

const transformUp = async (ddb, preparationData, isDryRun) => {
    console.info(` ${preparationData}`)
    const newItems = flatArray(preparationData.map((item) => {
        return up(item)
    }))

    if (!isDryRun) {
        await save(ddb, newItems)
    } else {
        console.info(newItems, 'updatedItems')
        console.info(newItems.length, 'updatedItems.length')
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


module.exports = {
    transformUp,
    // transformDown,
    prepare, // pass this function only if you need preparation data for the migration
    sequence: 1, // the migration number
}
