const outputs = require('../amplify_outputs.json');
console.log('User Pool ID:', outputs.auth.user_pool_id);
console.log('Client ID:', outputs.auth.user_pool_client_id);
console.log('Region:', outputs.auth.aws_region);
