const { utils } = require('dynamo-data-transform');
const { ScanCommand, TransactWriteCommand } = require('@aws-sdk/lib-dynamodb');

const TableName = 'Resources';

const getResources = async (ddb, lastEvalKey, resourceTypes) => {
    const params = {
        TableName,
        ExclusiveStartKey: lastEvalKey,
        FilterExpression: `#resource_type IN (:${resourceTypes.join(',:')}) AND #GSI2PK <> :resource_in_use`,
        ExpressionAttributeNames: {
            '#resource_type': 'resource_type',
            '#GSI2PK': 'GSI2PK',
        },
        ExpressionAttributeValues: {
            ...resourceTypes.reduce((acc, type) => ({ ...acc, [`:${type}`]: type }), {}),
            ':resource_in_use': 'ITEM_TYPE#resource_in_use',
        },
    };

    const queryCommand = new ScanCommand(params);
    return await ddb.send(queryCommand);
};

const createNewResource = (resource, newResourceType) => ({
    Put: {
        TableName,
        Item: {
            ...resource,
            resource_type: newResourceType,
            SK: `RESOURCE_TYPE#${newResourceType}`,
        },
    },
});

const deleteResource = (resource) => ({
    Delete: {
        TableName,
        Key: {
            PK: resource.PK,
            SK: resource.SK,
        },
    },
});

const transform = async ({ ddb, isDryRun, resourceTypes, typeMap }) => {
    let lastEvalKey = undefined;
    let transformed = 0;

    do {
        const { Items, LastEvaluatedKey } = await getResources(ddb, lastEvalKey, resourceTypes);
        lastEvalKey = LastEvaluatedKey;

        for (const item of Items) {
            const newResourceType = typeMap[item.resource_type];
            const newResourceItem = createNewResource(item, newResourceType);
            const deleteItem = deleteResource(item);

            const transactItems = [newResourceItem, deleteItem];

            if (!isDryRun) {
                await ddb.send(new TransactWriteCommand({ TransactItems: transactItems }));
                transformed += 1;
            } else {
                console.log('Dry run:', JSON.stringify(transactItems, null, 2));
                transformed += 1;
            }
        }
    } while (lastEvalKey);

    console.log(`Total transformed objects: ${transformed}`);
    return { transformed };
};

const transformUp = async ({ ddb, isDryRun }) => {
    const resourceTypes = ['github_actions', 'github_actions_high_priority'];
    const typeMap = {
        'github_actions': 'ci',
        'github_actions_high_priority': 'ci_high_priority',
    };

    return await transform({ ddb, isDryRun, resourceTypes, typeMap });
};

const transformDown = async ({ ddb, isDryRun }) => {
    const resourceTypes = ['ci', 'ci_high_priority'];
    const typeMap = {
        'ci': 'github_actions',
        'ci_high_priority': 'github_actions_high_priority',
    };

    return await transform({ ddb, isDryRun, resourceTypes, typeMap });
};

module.exports = {
    transformUp,
    transformDown,
    transformationNumber: 8,
};
