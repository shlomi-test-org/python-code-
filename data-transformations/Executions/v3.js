/*
This migration purpose is to delete executions that are older than 2 weeks.
 */

const { utils } = require('dynamo-data-transform');
const { ScanCommand } = require('@aws-sdk/lib-dynamodb');


const EXECUTIONS_TABLE = 'Executions';
const TWO_WEEKS_IN_MILLISECONDS = 1000 * 60 * 60 * 24 * 14;
const DATE_TWO_WEEKS_AGO = new Date(new Date() - TWO_WEEKS_IN_MILLISECONDS);
const ISO_DATE = DATE_TWO_WEEKS_AGO.toISOString();
const ISO_DATE_TWO_WEEKS_AGO = ISO_DATE.slice(0, ISO_DATE.length - 1) + '000';


const getExecutionFromDB = async (ddb, lastEvalKey, tableName) => {
  const params = {
    TableName: tableName,
    ExclusiveStartKey: lastEvalKey,
    Limit: 300,
  };

  const scanCommand = new ScanCommand(params);
  return await ddb.send(scanCommand);
}


function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}


const filterExecutions = (item) => ("created_at" in item && item.created_at < ISO_DATE_TWO_WEEKS_AGO);

/**
 * Fetch the items from the db in chunks of 25 each time and transform them using `transformer` function.
 * @param ddb
 * @param tableName
 * @param isDryRun
 * @returns {Promise<{transformed: number}>}
 */
const deleteOldExecutions = async (ddb, tableName, isDryRun) => {
  let lastEvalKey;
  let transformedCounter = 0;
  let scannedAllItems = false;

  while (!scannedAllItems) {
    const { Items, LastEvaluatedKey } = await getExecutionFromDB(ddb, lastEvalKey, tableName);
    console.info(`Got ${Items.length} items from dynamo`);
    lastEvalKey = LastEvaluatedKey;

    const filteredItemsToDelete = Items.filter(filterExecutions)

    if (filteredItemsToDelete?.length && filteredItemsToDelete.length > 0) {
      console.log(`Before deleting ${filteredItemsToDelete?.length} items lastEvalKey=  ${JSON.stringify(LastEvaluatedKey)}`)
      try {
        await utils.deleteItems(ddb, tableName, filteredItemsToDelete, isDryRun);
      } catch (deleteError) {
          console.log(deleteError, 'Error deleting items (possibly get threshold limit, continue deleting the rest');
          await sleep(1000);
          try {
            await utils.deleteItems(ddb, tableName, filteredItemsToDelete, isDryRun);
          }
          catch (deleteError) {
            console.log('Could not delete certain executions - please try again later');
          }

      }
      console.log(`After deleting ${filteredItemsToDelete?.length} items`)
      transformedCounter += filteredItemsToDelete.length;
    } else {
      console.info(filteredItemsToDelete, 'Going to delete');
    }
    scannedAllItems = !lastEvalKey;
  }

  return {
    transformed: transformedCounter,
  };
};

/**
 * @param {DynamoDBDocumentClient} ddb - dynamo db client of @aws-sdk https://docs.aws.amazon.com/AWSJavaScriptSDK/v3/latest/clients/client-dynamodb
 * @param {boolean} isDryRun
 * @returns the number of transformed items { transformed: number }
 *
 */
const transformUp = async ({ ddb, isDryRun}) => {
  return await deleteOldExecutions(ddb,
      EXECUTIONS_TABLE,
      isDryRun);
};

module.exports = {
    transformUp,
    transformationNumber: 3,
};
