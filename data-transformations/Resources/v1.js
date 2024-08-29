const {utils} = require('dynamo-data-transform');
const {ScanCommand} = require('@aws-sdk/lib-dynamodb');

const TABLE_NAME = 'Resources';

const RUNNERS = ['github_actions', 'jit'];

const getTenants = async (ddb) => {
    let lastEvalKey;
    let tenants = []
    do {
        const params = {
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
        }
        const scanCommand = new ScanCommand(params);
        const {Items, LastEvaluatedKey} = await ddb.send(scanCommand);
        tenants = [...tenants, ...Items]
        lastEvalKey = LastEvaluatedKey;
    } while (lastEvalKey)
    const tenants_ids = tenants.map(tenant => (tenant.tenant_id))
    return tenants_ids
}

const getResourcesRecords = async (ddb) => {
    let lastEvalKey;
    let resources_records = []
    do {
        const params = {
            TableName: TABLE_NAME,
            ExclusiveStartKey: lastEvalKey,
            FilterExpression: 'begins_with(#SK, :SK_prefix)',
            ExpressionAttributeNames: {
                '#SK': 'SK',
            },
            ExpressionAttributeValues: {
                ':SK_prefix': 'RUNNER',
            }
        }
        const scanCommand = new ScanCommand(params);
        const {Items, LastEvaluatedKey} = await ddb.send(scanCommand);
        resources_records = [...resources_records, ...Items]
        lastEvalKey = LastEvaluatedKey;
    } while (lastEvalKey)
    const tenants_ids_set = new Set(resources_records.map(resource_record => (resource_record.tenant_id)))
    const tenants_ids = [...tenants_ids_set]
    return tenants_ids
}

const get_tenants_without_resources_records = async (ddb) => {
    const tenants_ids = await getTenants(ddb);
    const tenant_ids_of_resources_records = await getResourcesRecords(ddb);
    const tenants_without_resources_records = tenants_ids.filter(tenant_id => !tenant_ids_of_resources_records.includes(tenant_id))
    return tenants_without_resources_records
}

const up = (tenant_id) => {
    return RUNNERS.map(runner => ({
        PK: `TENANT#${tenant_id}`,
        SK: `RUNNER#${runner}`,
        tenant_id,
        runner,
        max_resources_in_use: 10,
        resources_in_use: 0,
    }))
}

// The version of nodejs in the CI is 10.x which doesn't support .flat()
const flatArray = (arr) => {
    return arr.reduce((flat, toFlatten) => {
        return flat.concat(Array.isArray(toFlatten) ? flatArray(toFlatten) : toFlatten);
    }, []);
}

const transformUp = async ({ddb, isDryRun}) => {
    // Replace this with your own logic
    const tenants_without_records = await get_tenants_without_resources_records(ddb);
    console.log(`tenants_without_records: ${tenants_without_records}`)
    const newItems = flatArray(tenants_without_records.map((tenant_id) => {
        return up(tenant_id)
    }))
    return utils.insertItems(ddb, TABLE_NAME, newItems, isDryRun);
};

module.exports = {
    transformUp,
    // transformDown,
    // prepare, // export this function only if you need preparation data for the transformation
    transformationNumber: 1,
};
