/*
Dummy migration
We did a migration v2 that got to staging, but we decided not to get it to prod
so in staging transformationNumber: 2. this dummy is for you to do v3 and skip v2
 */

const transformUp = async ({ ddb, isDryRun}) => {
  return {
    transformed: 0,
  };
};


module.exports = {
  transformUp,
  transformationNumber: 2,
};
