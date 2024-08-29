const {utils} = require('dynamo-data-transform');
const {ScanCommand} = require('@aws-sdk/lib-dynamodb');

const TableName = 'Resources';

const getResourceItemsToDelete = async (ddb, lastEvalKey) => {
    const params = {
        TableName: TableName,
        ExclusiveStartKey: lastEvalKey,
        FilterExpression: 'begins_with(#SK, :SK_prefix)',
        ExpressionAttributeNames: {
            '#SK': 'SK',
        },
        ExpressionAttributeValues: {
            ':SK_prefix': 'RUNNER#',
        }
    }

    const scanCommand = new ScanCommand(params);
    return await ddb.send(scanCommand);
};

const getResourceItemsToCreate = async (ddb, lastEvalKey) => {
    const params = {
        TableName: TableName,
        ExclusiveStartKey: lastEvalKey,
        FilterExpression: 'begins_with(#SK, :SK_prefix)',
        ExpressionAttributeNames: {
            '#SK': 'SK',
        },
        ExpressionAttributeValues: {
            ':SK_prefix': 'RESOURCE_TYPE#',
        }
    }

    const scanCommand = new ScanCommand(params);
    return await ddb.send(scanCommand);
};

const down = (item) => (
    {
        ...item,
        "SK": `RUNNER#${item.resource_type}`,
        "resources_in_use": 0,
        "runner": item.resource_type
    })

const transformDown = async ({ddb, isDryRun}) => {
    let lastEvalKey = undefined;
    let transformed = 0;
    do {
        const {Items, LastEvaluatedKey} = await getResourceItemsToCreate(ddb, lastEvalKey);
        lastEvalKey = LastEvaluatedKey;

        const updatedItems = Items.map(item => down(item));
        if (isDryRun) {
            console.log(updatedItems);
            await utils.insertItems(ddb, TableName, updatedItems, isDryRun);
            transformed += updatedItems.length;
        } else {
            const {transformed: itemsTransformed} = await utils.insertItems(ddb, TableName, updatedItems, isDryRun);
            transformed += itemsTransformed;
        }
    } while (lastEvalKey);

    return {transformed};
};

const transformUp = async ({ddb, isDryRun}) => {
    let lastEvalKey = undefined;
    let transformed = 0;
    do {
        const {Items, LastEvaluatedKey} = await getResourceItemsToDelete(ddb, lastEvalKey);
        lastEvalKey = LastEvaluatedKey;

        if (isDryRun) {
            console.log(Items);
            await utils.deleteItems(ddb, TableName, Items, isDryRun);
            transformed += Items.length;
        } else {
            const {transformed: itemsTransformed} = await utils.deleteItems(ddb, TableName, Items, isDryRun);
            transformed += itemsTransformed;
        }
    } while (lastEvalKey);

    return {transformed};
};

module.exports = {
    transformUp,
    transformDown,
    transformationNumber: 5
};
