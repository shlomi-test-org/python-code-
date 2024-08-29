const {utils} = require('dynamo-data-transform');
const {ScanCommand} = require('@aws-sdk/lib-dynamodb');

const TableName = 'Resources';
const new_resources = ['github_actions_high_priority', 'jit_high_priority']
const UNLIMITED_MAX_RESOURCES_IN_USE = 1000000

const getTenants = async (ddb, lastEvalKey) => {
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
        ProjectionExpression: 'tenant_id'
    }

    const queryCommand = new ScanCommand(params);
    return await ddb.send(queryCommand);
};

// The version of nodejs in the CI is 10.x which doesn't support .flat()
const flatArray = (arr) => {
    return arr.reduce((flat, toFlatten) => {
        return flat.concat(Array.isArray(toFlatten) ? flatArray(toFlatten) : toFlatten);
    }, []);
}

const up = (tenant_id) => (
    new_resources.map(new_resource => ({
            PK: `TENANT#${tenant_id}`,
            SK: `RUNNER#${new_resource}`,
            tenant_id,
            runner: new_resource,
            resources_in_use: 0,
            max_resources_in_use: UNLIMITED_MAX_RESOURCES_IN_USE,
        })
    )
)

const transformUp = async ({ddb, isDryRun}) => {
    let lastEvalKey = undefined;
    let transformed = 0;
    do {
        const {Items, LastEvaluatedKey} = await getTenants(ddb, lastEvalKey);
        console.log(`Found ${Items.length} tenants`);
        lastEvalKey = LastEvaluatedKey;

        const itemsToAdd = flatArray(Items.map(item => up(item.tenant_id)));
        if (isDryRun) {
            await utils.insertItems(ddb, TableName, itemsToAdd, isDryRun);
            transformed += itemsToAdd.length;
        } else {
            const {transformed: itemsTransformed} = await utils.insertItems(
                ddb,
                TableName,
                itemsToAdd,
                isDryRun
            );
            transformed += itemsTransformed;
        }
    } while (lastEvalKey);

    return {transformed};
};

module.exports = {
    transformUp,
    transformationNumber: 2,
};
