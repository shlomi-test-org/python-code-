/*
This migration purpose is to delete executions that are older than 2 weeks.
 */

const { utils } = require('dynamo-data-transform');
const { QueryCommand, ScanCommand } = require('@aws-sdk/lib-dynamodb');


const EXECUTIONS_TABLE = 'Executions';

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
    const { Items, LastEvaluatedKey } = await ddb.send(scanCommand);
    tenants = [...tenants, ...Items]
    lastEvalKey = LastEvaluatedKey;
  } while (lastEvalKey)
  const tenants_ids = tenants.map(tenant => (tenant.tenant_id))
  return tenants_ids
}


const getExecutionFromDB = async (ddb, tableName, tenantId, lastKey) => {
  // Get all Pending executions with jit_event_name 'trigger_scheduled_task'
  const params = {
    TableName: EXECUTIONS_TABLE,
    IndexName: 'GSI2',
    KeyConditionExpression: 'GSI2PK = :gsi2pk AND begins_with(GSI2SK, :created_at)',
    FilterExpression: '#jit_event_name = :jit_event_name',
    ExpressionAttributeNames: {
      '#jit_event_name': 'jit_event_name',
    },
    ExpressionAttributeValues: {
      ':gsi2pk': `TENANT#${tenantId}#STATUS#pending`,
      ':jit_event_name': 'trigger_scheduled_task',
      ':created_at': '2024-04-07',
    },
  };
  if (lastKey) {
    params.ExclusiveStartKey = lastKey;
  }

  const scanCommand = new QueryCommand(params);
  const res = await ddb.send(scanCommand);
  return res
}


function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}


/**
 * @param {DynamoDBDocumentClient} ddb - dynamo db client of @aws-sdk https://docs.aws.amazon.com/AWSJavaScriptSDK/v3/latest/clients/client-dynamodb
 * @param {boolean} isDryRun
 * @returns the number of transformed items { transformed: number }
 *
 */
const transformUp = async ({ ddb, isDryRun }) => {
  let allTenants = await getTenants(ddb);
  // Start from index 470
  allTenants = allTenants.slice(470);

  let transformedCounter = 0;
  let itemsToDelete = [];
  for (const tenantId of allTenants) {
    await sleep(1000);
    let lastEvalKey = null;
    console.log(`----------------------\nHandling Tenant: ${tenantId}`)
    while (true) {
      const { Items, LastEvaluatedKey } = await getExecutionFromDB(ddb, EXECUTIONS_TABLE, tenantId, lastEvalKey);
      console.info(`Got ${Items.length} items from dynamo`);
      lastEvalKey = LastEvaluatedKey;
      itemsToDelete = [...itemsToDelete, ...Items]
      if (!LastEvaluatedKey) {
        console.log(`LastEvaluatedKey is null`);
        console.log(`Total items to delete: ${itemsToDelete.length}`);
        if (itemsToDelete.length === 0) {
          break;
        }
        for (let i = 0; i < 5; i++) {
          try {
            await utils.deleteItems(ddb, EXECUTIONS_TABLE, itemsToDelete, isDryRun);
            break;
          } catch (deleteError) {
            console.log('Error deleting items (possibly get threshold limit, Retrying)');
            await sleep(2000);
          }
          itemsToDelete = [];
          break;
        }
      }
      transformedCounter += Items.length;
    }
  }
  console.log(`Deleting ${itemsToDelete.length} items`)
  await utils.deleteItems(ddb, EXECUTIONS_TABLE, itemsToDelete, isDryRun);


  return { transformed: transformedCounter };
};

module.exports = {
  transformUp,
  transformationNumber: 4,
};
