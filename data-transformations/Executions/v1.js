const { utils } = require('dynamo-data-transform');
const { QueryCommand } = require('@aws-sdk/lib-dynamodb');
const NeuroBladeRemovedAssets = [
  '000e3c6c-c2e8-4005-a3b2-e331d5925bd1',
  '02bc2a5c-7e40-43e8-a5c8-7b6d9f9798d8',
  '0a611cb0-f903-4809-b102-97d0f1fc1d24',
  '152e80f7-18c8-416f-85c7-e92e3085f382',
  '35a469c7-a12b-443b-b511-88e5f4772ecd',
  '477c72ea-dce4-4e1a-a43e-2868b13ea4e3',
  '55faa664-4520-44d0-87cb-8e3ac6930a43',
  '67578496-eb1d-4f8f-b1e4-81752391f224',
  '6a52deb8-a12e-4cb2-b34d-4b9d339dec64',
  '6a7313ce-b8fc-4b7b-802a-1b25b63b70b0',
  '6eea4c80-baae-43cd-b09d-123e24fddc81',
  '780d0eee-e987-48c7-8bd0-777a4139c0a1',
  '9ae4cba2-b34d-400c-820f-62ecba8b4237',
  'a1465184-a874-4aeb-aa9f-7c32f0b5bc98',
  'a742e92e-61ba-4db6-bfc9-76730b890f28',
  'bb7ab6d6-8854-40af-bb49-44cbe8a149c8',
  'c31e0fdd-8faa-4bb2-becb-3ca5857f0746',
  'c7741e56-3b83-4abc-a955-1a7acfe69cdb',
  'ce8dbfe4-30a0-40b5-8dbf-02b0ed8e693c',
  'd3f520b9-f7ef-4137-8ad9-aa065bbd341d',
  'dc9b07c1-d034-4db6-8128-daca805dfa54',
  'deca6918-c31f-4d37-b69a-85b109f7baf4',
  'e449f6e5-cde2-4d74-a3e2-2f92daee7952',
  'e6c71d71-a0cd-4fec-b6a0-95572e5d52ee',
];

const TableName = 'Executions';

const getAssetsByIds = async (ddb, lastEvalKey) => {
  neuroBladeAssetIdObject = {};
  NeuroBladeRemovedAssets.forEach((value, index) => {
    const assetIdKey = ':asset_id' + index;
    neuroBladeAssetIdObject[assetIdKey.toString()] = value;
  });

  PK = 'TENANT#168d5ba8-2e13-45e0-8800-fd2b50f66cd5';
  const params = {
    TableName,
    KeyConditionExpression: '#PK = :pk',
    FilterExpression:
      'asset_id IN (' +
      Object.keys(neuroBladeAssetIdObject).toString() +
      ') AND #status = :status',
    ExpressionAttributeNames: {
      '#PK': 'PK',
      '#status': 'status',
    },
    ExpressionAttributeValues: {
      ':pk': PK,
      ':status': 'pending',
      ...neuroBladeAssetIdObject,
    },
    ExclusiveStartKey: lastEvalKey,
  };

  const queryCommand = new QueryCommand(params);
  return await ddb.send(queryCommand);
};


const transformUp = async ({ ddb, isDryRun }) => {
  let lastEvalKey;
  let totalItems = 0;
  do {
    const { Items, LastEvaluatedKey } = await getAssetsByIds(ddb, lastEvalKey);
    lastEvalKey = LastEvaluatedKey;

    if (isDryRun) {
      await utils.deleteItems(ddb, TableName, Items, isDryRun);
      totalItems += Items.length;
    } else {
      const { transformed } = await utils.deleteItems(
        ddb,
        TableName,
        Items,
        isDryRun
      );
      totalItems += transformed;
    }
  } while (lastEvalKey);
  console.log(totalItems);

  return { transformed: totalItems };
};

module.exports = {
  transformUp,
  transformationNumber: 1,
};
