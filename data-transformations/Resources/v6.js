const {utils} = require('dynamo-data-transform');
const {QueryCommand, ScanCommand} = require('@aws-sdk/lib-dynamodb');

const TABLE_NAME = 'Resources';
const TENANTS_TABLE_NAME = 'Tenants';


const getTenantByTenantId = async (ddb, tenant_id) => {
    const params = {
        TableName: TENANTS_TABLE_NAME,
        KeyConditionExpression: '#PK = :pk',
        ExpressionAttributeNames: {
            '#PK': 'PK',
        },
        ExpressionAttributeValues: {
            ':pk': `TENANT#${tenant_id}`,
        }
    }
    const queryCommand = new QueryCommand(params);
    const {Items} = await ddb.send(queryCommand);
    return Items
}


const getResourcesGroupedByTenantId = async (ddb, lastEvalKey) => {
    const params = {
        TableName: TABLE_NAME,
        ExclusiveStartKey: lastEvalKey,
        FilterExpression: 'begins_with(#PK, :PK_prefix)',
        ExpressionAttributeNames: {
            '#PK': 'PK',
        },
        ExpressionAttributeValues: {
            ':PK_prefix': 'TENANT',
        }
    }
    const scanCommand = new ScanCommand(params);
    const {Items, LastEvaluatedKey} = await ddb.send(scanCommand);
    lastEvalKey = LastEvaluatedKey;

    const resourcesGroupedByTenantId = {};
    Items.forEach(item => {
        const tenantId = item.tenant_id;
        if (!resourcesGroupedByTenantId[tenantId]) {
            resourcesGroupedByTenantId[tenantId] = [];
        }
        resourcesGroupedByTenantId[tenantId].push(item);
    });
    return {
        resourcesGroupedByTenantId,
        LastEvaluatedKey: lastEvalKey
    }
}

const getResourcesToDelete = async (ddb, resourcesGroupedByTenantId) => {
    const resourcesToDelete = [];
    const tenantIds = Object.keys(resourcesGroupedByTenantId);
    const tenantsIdsToDelete = new Set()
    for (const tenantId of tenantIds) {
        const tenant = await getTenantByTenantId(ddb, tenantId);
        if (tenant.length === 0) {
            tenantsIdsToDelete.add(tenantId)
            resourcesToDelete.push(...resourcesGroupedByTenantId[tenantId]);
        }
    }
    return {
        resourcesToDelete,
        tenantsIdsToDelete
    };
}


const transformUp = async ({ddb, isDryRun}) => {
    let lastEvalKey;
    let totalItems = 0;
    let tenantsIdsToDeleteAll = new Set();
    do {
        const {resourcesGroupedByTenantId, LastEvaluatedKey} = await getResourcesGroupedByTenantId(ddb, lastEvalKey);
        lastEvalKey = LastEvaluatedKey;
        const {resourcesToDelete, tenantsIdsToDelete} = await getResourcesToDelete(ddb, resourcesGroupedByTenantId);
        tenantsIdsToDeleteAll = new Set([...tenantsIdsToDeleteAll, ...tenantsIdsToDelete]);
        if (isDryRun) {
            await utils.deleteItems(ddb, TABLE_NAME, resourcesToDelete, isDryRun);
            totalItems += resourcesToDelete.length;
        } else {
            const {transformed} = await utils.deleteItems(
                ddb,
                TABLE_NAME,
                resourcesToDelete,
                isDryRun
            );
            totalItems += transformed;
        }
    } while (lastEvalKey);
    console.log(totalItems);
    console.log(`Tenants to delete length: ${tenantsIdsToDeleteAll.size}`);
    console.log(tenantsIdsToDeleteAll);

    return {transformed: totalItems};
};

module.exports = {
    transformUp,
    transformationNumber: 6,
};
