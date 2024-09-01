const {utils} = require('dynamo-data-transform');
const {ScanCommand} = require('@aws-sdk/lib-dynamodb');

const TableName = 'Resources';

const getResourceItems = async (ddb, lastEvalKey) => {
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

const up = (item) => (
    {...item, resource_type: item.runner}
)

const transformUp = async ({ddb, isDryRun}) => {
    let lastEvalKey = undefined;
    let transformed = 0;
    do {
        const {Items, LastEvaluatedKey} = await getResourceItems(ddb, lastEvalKey);
        lastEvalKey = LastEvaluatedKey;

        const updatedItems = Items.map(item => up(item));
        if (isDryRun) {
            console.log(updatedItems);
            await utils.insertItems(ddb, TableName, updatedItems, isDryRun);
            transformed += updatedItems.length;
        } else {
            const {transformed: itemsTransformed} = await utils.insertItems(
                ddb,
                TableName,
                updatedItems,
                isDryRun
            );
            transformed += itemsTransformed;
        }
    } while (lastEvalKey);

    return {transformed};
};

module.exports = {
    transformUp,
    transformationNumber: 3,
};
