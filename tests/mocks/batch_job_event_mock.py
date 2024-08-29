MOCK_BATCH_FAILURE_EVENT = {
    "version": "0",
    "id": "c3ba0a36-523d-b777-916b-cb321eca9250",
    "detail-type": "Batch Job State Change",
    "source": "aws.batch",
    "account": "963685750466",
    "event_time": "2022-11-13T08:59:01Z",
    "region": "us-east-1",
    "resources": [
        "arn:aws:batch:us-east-1:963685750466:job/a7c17e65-6eb9-4d5c-ad20-90ae910f6660"
    ],
    "detail": {
        "jobArn": "arn:aws:batch:us-east-1:963685750466:job/a7c17e65-6eb9-4d5c-ad20-90ae910f6660",
        "jobName": "5f79e351-1e4f-430f-a0c7-45f0ad90c0bd",
        "jobId": "a7c17e65-6eb9-4d5c-ad20-90ae910f6660",
        "jobQueue": "arn:aws:batch:us-east-1:963685750466:job-queue/fargate-tasks-queue",
        "status": "FAILED",
        "attempts": [
            {
                "container": {
                    "taskArn": "arn:aws:ecs:us-east-1:963685750466:task/"
                    "AWSBatch-fargate-batch-compute-a9b789f0"
                    "-f35e-396f-9c0f-50e00abf809f/332089cce2794bfeb27186563687041f",
                    "exitCode": 1,
                    "logStreamName": "ecs/default/332089cce2794bfeb27186563687041f",
                    "networkInterfaces": [
                        {
                            "attachmentId": "16540900-a275-404c-8171-bc1c8baf4eb1",
                            "privateIpv4Address": "10.0.0.227",
                        }
                    ],
                },
                "startedAt": 1668329909107,
                "stoppedAt": 1668329941236,
                "statusReason": "Essential container in task exited",
            }
        ],
        "statusReason": "Essential container in task exited",
        "createdAt": 1668329821438,
        "startedAt": 1668329909107,
        "stoppedAt": 1668329941236,
        "dependsOn": [],
        "jobDefinition": "arn:aws:batch:us-east-1:963685750466:job-definition/web-app-scanner:1",
        "parameters": {},
        "container": {
            "image": "963685750466.dkr.ecr.us-east-1.amazonaws.com/web-app-scanner:latest",
            "command": [],
            "executionRoleArn": "arn:aws:iam::963685750466:role/ecs_task_role",
            "volumes": [],
            "environment": [],
            "mountPoints": [],
            "ulimits": [],
            "exitCode": 1,
            "taskArn": "arn:aws:ecs:us-east-1:963685750466:task/AWSBatch-fargate-batch"
            "-compute-a9b789f0-f35e-396f-9c0f-50e00abf809f"
            "/332089cce2794bfeb27186563687041f",
            "logStreamName": "ecs/default/332089cce2794bfeb27186563687041f",
            "networkInterfaces": [
                {
                    "attachmentId": "16540900-a275-404c-8171-bc1c8baf4eb1",
                    "privateIpv4Address": "10.0.0.227",
                }
            ],
            "resourceRequirements": [
                {"value": "0.5", "type": "VCPU"},
                {"value": "2048", "type": "MEMORY"},
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/web-app-scanner-container",
                    "awslogs-stream-prefix": "ecs",
                },
                "secretOptions": [],
            },
            "secrets": [],
            "fargatePlatformConfiguration": {"platformVersion": "LATEST"},
        },
        "tags": {
            "resourceArn": "arn:aws:batch:us-east-1:963685750466:job/"
            "a7c17e65-6eb9-4d5c-ad20-90ae910f6660"
        },
        "propagateTags": False,
        "platformCapabilities": ["FARGATE"],
        "eksAttempts": [],
    },
}

MOCK_ECS_EVENT = {
    "version": "0",
    "id": "c28d36a5-76dd-70e0-1c42-7bdfa5fd6fb5",
    "detail-type": "ECS Task State Change",
    "source": "aws.ecs",
    "account": "121169888995",
    "event_time": "2022-11-23T16:37:19Z",
    "region": "us-east-1",
    "resources": [
        "arn:aws:ecs:us-east-1:121169888995:task/AWSBatch-fargate-batch-compute-13af15fe-56c9-38e0-b28e-a4300c63c0d"
    ],
    "detail": {
        "attachments": [
            {
                "id": "8d24047b-5494-4741-a50c-974626d44f09",
                "type": "eni",
                "status": "DELETED",
                "details": [
                    {"name": "subnetId", "value": "subnet-0e835c968ae0c3dff"},
                    {"name": "networkInterfaceId", "value": "eni-077629efe323ef919"},
                    {"name": "macAddress", "value": "02:02:f2:ef:52:89"},
                    {"name": "privateIPv4Address", "value": "10.0.0.243"},
                ],
            }
        ],
        "attributes": [{"name": "ecs.cpu-architecture", "value": "x86_64"}],
        "availabilityZone": "us-east-1a",
        "capacityProviderName": "FARGATE",
        "clusterArn": "arn:aws:ecs:us-east-1:121169888995:cluster/AWSBatch-fargate-batch-compute-13af15fe-56c9-3",
        "connectivity": "CONNECTED",
        "connectivityAt": "2022-11-23T16:36:22.924Z",
        "containers": [
            {
                "containerArn": "arn:aws:ecs:us-east-1:121169888995:container/AWSBatch-fargate-batch-compute-13af",
                "exitCode": 0,
                "lastStatus": "STOPPED",
                "name": "default",
                "image": "121169888995.dkr.ecr.us-east-1.amazonaws.com/prowler:latest",
                "imageDigest": "sha256:f1279d66c3547e70c738376225adf59cd9b1b5f899841d07ce64c7fc83d8779a",
                "runtimeId": "645fdc17232c49c9951509d12e376d20-2470140894",
                "taskArn": "arn:aws:ecs:us-east-1:121169888995:task/AWSBatch-fargate-batch-compute-13af15fe-5",
                "networkInterfaces": [
                    {
                        "attachmentId": "8d24047b-5494-4741-a50c-974626d44f09",
                        "privateIpv4Address": "10.0.0.243",
                    }
                ],
                "cpu": "0",
            }
        ],
        "cpu": "512",
        "createdAt": "2022-11-23T16:36:18.708Z",
        "desiredStatus": "STOPPED",
        "enableExecuteCommand": False,
        "ephemeralStorage": {"sizeInGiB": 30},
        "executionStoppedAt": "2022-11-23T16:36:56.225Z",
        "group": "family:prowler",
        "launchType": "FARGATE",
        "lastStatus": "STOPPED",
        "memory": "2048",
        "overrides": {
            "containerOverrides": [
                {
                    "environment": [],
                    "name": "default",
                }
            ],
            "cpu": "512",
            "memory": "2048",
        },
        "platformVersion": "1.4.0",
        "pullStartedAt": "2022-11-23T16:36:31.21Z",
        "pullStoppedAt": "2022-11-23T16:36:41.153Z",
        "startedAt": "2022-11-23T16:36:46.101Z",
        "stoppingAt": "2022-11-23T16:37:06.432Z",
        "stoppedAt": "2022-11-23T16:37:19.295Z",
        "stoppedReason": "Essential container in task exited",
        "stopCode": "EssentialContainerExited",
        "taskArn": "arn:aws:ecs:us-east-1:121169888995:task/AWSBatch-fargate-batch-compute-13af15fe-",
        "taskDefinitionArn": "arn:aws:ecs:us-east-1:121169888995:task-definition/prowler:5",
        "updatedAt": "2022-11-23T16:37:19.295Z",
        "version": 5,
    },
}

MOCK_ECS_EVENT_TWO_CONTAINERS = {
    "version": "0",
    "id": "c28d36a5-76dd-70e0-1c42-7bdfa5fd6fb5",
    "detail-type": "ECS Task State Change",
    "source": "aws.ecs",
    "account": "121169888995",
    "event_time": "2022-11-23T16:37:19Z",
    "region": "us-east-1",
    "resources": [
        "arn:aws:ecs:us-east-1:121169888995:task/AWSBatch-fargate-batch-compute-13af15fe-56c9-38e0-b28e-a4300c63c0d"
    ],
    "detail": {
        "attachments": [
            {
                "id": "8d24047b-5494-4741-a50c-974626d44f09",
                "type": "eni",
                "status": "DELETED",
                "details": [
                    {"name": "subnetId", "value": "subnet-0e835c968ae0c3dff"},
                    {"name": "networkInterfaceId", "value": "eni-077629efe323ef919"},
                    {"name": "macAddress", "value": "02:02:f2:ef:52:89"},
                    {"name": "privateIPv4Address", "value": "10.0.0.243"},
                ],
            }
        ],
        "attributes": [{"name": "ecs.cpu-architecture", "value": "x86_64"}],
        "availabilityZone": "us-east-1a",
        "capacityProviderName": "FARGATE",
        "clusterArn": "arn:aws:ecs:us-east-1:121169888995:cluster/AWSBatch-fargate-batch-compute-13af15fe-56c9-3",
        "connectivity": "CONNECTED",
        "connectivityAt": "2022-11-23T16:36:22.924Z",
        "containers": [
            {
                "containerArn": "arn:aws:ecs:us-east-1:121169888995:container/AWSBatch-fargate-batch-compute-13af",
                "exitCode": 999,
                "lastStatus": "STOPPED",
                "name": "default",
                "image": "first",
                "imageDigest": "12345",
                "runtimeId": "645fdc17232c49c9951509d12e376d20-2470140894",
                "taskArn": "arn:aws:ecs:us-east-1:121169888995:task/AWSBatch-fargate-batch-compute-13af15fe-5",
                "networkInterfaces": [
                    {
                        "attachmentId": "8d24047b-5494-4741-a50c-974626d44f09",
                        "privateIpv4Address": "10.0.0.243",
                    }
                ],
                "cpu": "0",
            },
            {
                "containerArn": "arn:aws:ecs:us-east-1:121169888995:container/AWSBatch-fargate-batch-compute-13af",
                "exitCode": 0,
                "lastStatus": "STOPPED",
                "name": "default",
                "image": "121169888995.dkr.ecr.us-east-1.amazonaws.com/prowler:latest",
                "imageDigest": "sha256:f1279d66c3547e70c738376225adf59cd9b1b5f899841d07ce64c7fc83d8779a",
                "runtimeId": "645fdc17232c49c9951509d12e376d20-2470140894",
                "taskArn": "arn:aws:ecs:us-east-1:121169888995:task/AWSBatch-fargate-batch-compute-13af15fe-5",
                "networkInterfaces": [
                    {
                        "attachmentId": "8d24047b-5494-4741-a50c-974626d44f09",
                        "privateIpv4Address": "10.0.0.243",
                    }
                ],
                "cpu": "0",
            },
        ],
        "cpu": "512",
        "createdAt": "2022-11-23T16:36:18.708Z",
        "desiredStatus": "STOPPED",
        "enableExecuteCommand": False,
        "ephemeralStorage": {"sizeInGiB": 20},
        "executionStoppedAt": "2022-11-23T16:36:56.225Z",
        "group": "family:prowler",
        "launchType": "FARGATE",
        "lastStatus": "STOPPED",
        "memory": "2048",
        "overrides": {
            "containerOverrides": [
                {
                    "environment": [],
                    "name": "default",
                }
            ],
            "cpu": "512",
            "memory": "2048",
        },
        "platformVersion": "1.4.0",
        "pullStartedAt": "2022-11-23T16:36:31.21Z",
        "pullStoppedAt": "2022-11-23T16:36:41.153Z",
        "startedAt": "2022-11-23T16:36:46.101Z",
        "stoppingAt": "2022-11-23T16:37:06.432Z",
        "stoppedAt": "2022-11-23T16:37:19.295Z",
        "stoppedReason": "Essential container in task exited",
        "stopCode": "EssentialContainerExited",
        "taskArn": "arn:aws:ecs:us-east-1:121169888995:task/AWSBatch-fargate-batch-compute-13af15fe-",
        "taskDefinitionArn": "arn:aws:ecs:us-east-1:121169888995:task-definition/prowler:5",
        "updatedAt": "2022-11-23T16:37:19.295Z",
        "version": 5,
    },
}

MOCK_NON_JIT_EVENT = {
    "version": "0",
    "id": "a0449042-4803-369c-8cfb-3ae6d8a406c7",
    "detail-type": "ECS Task State Change",
    "source": "aws.ecs",
    "account": "121169888995",
    "event_time": "2022-11-29T09:35:31Z",
    "region": "us-east-1",
    "resources": [
        "arn:aws:ecs:us-east-1:121169888995:task/AWSBatch-fargate-batch-compute-13a"
    ],
    "detail": {
        "attachments": [
            {
                "id": "0cca28a3-0498-4a63-8bd9-d458c5c2cea4",
                "type": "eni",
                "status": "DELETED",
                "details": [
                    {"name": "subnetId", "value": "subnet-0491cb7a2631cdcdb"},
                    {"name": "networkInterfaceId", "value": "eni-02909d9838a10faab"},
                    {"name": "macAddress", "value": "16:99:fe:cd:1b:d7"},
                    {"name": "privateDnsName", "value": "ip-172-31-76-23.ec2.internal"},
                    {"name": "privateIPv4Address", "value": "172.31.76.23"},
                ],
            }
        ],
        "attributes": [{"name": "ecs.cpu-architecture", "value": "x86_64"}],
        "availabilityZone": "us-east-1f",
        "capacityProviderName": "FARGATE",
        "clusterArn": "arn:aws:ecs:us-east-1:121169888995:cluster/AWSBatch-fargate-batch",
        "connectivity": "CONNECTED",
        "connectivityAt": "2022-11-29T09:33:05.969Z",
        "containers": [
            {
                "containerArn": "arn:aws:ecs:us-east-1:121169888995:container/AWSBatch-farga",
                "exitCode": 0,
                "lastStatus": "STOPPED",
                "name": "test",
                "image": "mcr.microsoft.com/windows/nanoserver:ltsc2019",
                "runtimeId": "b0b33a742be74dfbb314e00ce54250a7-2949673445",
                "taskArn": "arn:aws:ecs:us-east-1:121169888995:task/AWSBatch-fargate-batch-compute-",
                "networkInterfaces": [
                    {
                        "attachmentId": "0cca28a3-0498-4a63-8bd9-d458c5c2cea4",
                        "privateIpv4Address": "172.31.76.23",
                    }
                ],
                "cpu": "0",
            }
        ],
        "cpu": "1024",
        "createdAt": "2022-11-29T09:31:02.672Z",
        "desiredStatus": "STOPPED",
        "enableExecuteCommand": False,
        "ephemeralStorage": {"sizeInGiB": 20},
        "executionStoppedAt": "2022-11-29T09:35:07.515Z",
        "group": "service:testtest",
        "launchType": "FARGATE",
        "lastStatus": "STOPPED",
        "memory": "3072",
        "overrides": {"containerOverrides": [{"name": "test"}]},
        "platformFamily": "Windows-Server-2019-Core",
        "platformVersion": "1.0.0",
        "pullStartedAt": "2022-11-29T09:34:31.21Z",
        "pullStoppedAt": "2022-11-29T09:34:53.653Z",
        "startedAt": "2022-11-29T09:34:57.144Z",
        "startedBy": "ecs-svc/6811052232430672964",
        "stoppingAt": "2022-11-29T09:35:18.808Z",
        "stoppedAt": "2022-11-29T09:35:31.949Z",
        "stoppedReason": "Essential container in task exited",
        "stopCode": "EssentialContainerExited",
        "taskArn": "arn:aws:ecs:us-east-1:121169888995:task/AWSBatch-fargate-7",
        "taskDefinitionArn": "arn:aws:ecs:us-east-1:121169888995:task-definition/windowstest:1",
        "updatedAt": "2022-11-29T09:35:31.949Z",
        "version": 6,
    },
}


MOCK_WINDOWS_CONTAINER = {
    "version": "0",
    "id": "a0449042-4803-369c-8cfb-3ae6d8a406c7",
    "detail-type": "ECS Task State Change",
    "source": "aws.ecs",
    "account": "121169888995",
    "event_time": "2022-11-29T09:35:31Z",
    "region": "us-east-1",
    "resources": [
        "arn:aws:ecs:us-east-1:121169888995:task/AWSBatch-fargate-batch-compute-13a250a7"
    ],
    "detail": {
        "attachments": [
            {
                "id": "0cca28a3-0498-4a63-8bd9-d458c5c2cea4",
                "type": "eni",
                "status": "DELETED",
                "details": [
                    {"name": "subnetId", "value": "subnet-0491cb7a2631cdcdb"},
                    {"name": "networkInterfaceId", "value": "eni-02909d9838a10faab"},
                    {"name": "macAddress", "value": "16:99:fe:cd:1b:d7"},
                    {"name": "privateDnsName", "value": "ip-172-31-76-23.ec2.internal"},
                    {"name": "privateIPv4Address", "value": "172.31.76.23"},
                ],
            }
        ],
        "attributes": [{"name": "ecs.cpu-architecture", "value": "x86_64"}],
        "availabilityZone": "us-east-1f",
        "capacityProviderName": "FARGATE",
        "clusterArn": "arn:aws:ecs:us-east-1:121169888995:cluster/AWSBatc4300c63c0dc",
        "connectivity": "CONNECTED",
        "connectivityAt": "2022-11-29T09:33:05.969Z",
        "containers": [
            {
                "containerArn": "arn:aws:ecs:us-east-1:121169888995:container/AWSBatch-fdac5b973d45",
                "exitCode": 0,
                "lastStatus": "STOPPED",
                "name": "default",
                "image": "mcr.microsoft.com/windows/nanoserver:ltsc2019",
                "runtimeId": "b0b33a742be74dfbb314e00ce54250a7-2949673445",
                "taskArn": "arn:aws:ecs:us-east-1:121169888995:task/AWSBatch-fargate-b4e00ce54250a7",
                "networkInterfaces": [
                    {
                        "attachmentId": "0cca28a3-0498-4a63-8bd9-d458c5c2cea4",
                        "privateIpv4Address": "172.31.76.23",
                    }
                ],
                "cpu": "0",
            }
        ],
        "cpu": "1024",
        "createdAt": "2022-11-29T09:31:02.672Z",
        "desiredStatus": "STOPPED",
        "enableExecuteCommand": False,
        "ephemeralStorage": {"sizeInGiB": 50},
        "executionStoppedAt": "2022-11-29T09:35:07.515Z",
        "group": "service:testtest",
        "launchType": "FARGATE",
        "lastStatus": "STOPPED",
        "memory": "3072",
        "overrides": {
            "containerOverrides": [
                {
                    "environment": [],
                    "name": "default",
                }
            ],
            "cpu": "512",
            "memory": "2048",
        },
        "platformFamily": "Windows-Server-2019-Core",
        "platformVersion": "1.0.0",
        "pullStartedAt": "2022-11-29T09:34:31.21Z",
        "pullStoppedAt": "2022-11-29T09:34:53.653Z",
        "startedAt": "2022-11-29T09:34:57.144Z",
        "startedBy": "ecs-svc/6811052232430672964",
        "stoppingAt": "2022-11-29T09:35:18.808Z",
        "stoppedAt": "2022-11-29T09:37:31Z",
        "stoppedReason": "Essential container in task exited",
        "stopCode": "EssentialContainerExited",
        "taskArn": "arn:aws:ecs:us-east-1:121169888995:task/AWSBatch-fargate-batch-compute-13af15fe-0a7",
        "taskDefinitionArn": "arn:aws:ecs:us-east-1:121169888995:task-definition/windowstest:1",
        "updatedAt": "2022-11-29T09:35:31.949Z",
        "version": 6,
    },
}

MOCK_PRICING_RESULT = {
    "FormatVersion": "aws_v1",
    "PriceList": [
        '{"product":{"productFamily":"Compute","attributes":{"regionCode":"us-east-1","servicecode":"AmazonECS",'
        '"usagetype":"USE1-Fargate-EphemeralStorage-GB-Hours","locationType":"AWS Region","location":'
        '"US East (N. Virginia)","servicename":"Amazon Elastic Container Service","operation":"",'
        '"storagetype":"default"},"sku":"7KPDPTDSCT4J3Z64"},"serviceCode":"AmazonECS",'
        '"terms":{"OnDemand":{"7KPDPTDSCT4J3Z64.JRTCKXETXF":{"priceDimensions":'
        '{"7KPDPTDSCT4J3Z64.JRTCKXETXF.6YS6EN2CT7":'
        '{"unit":"GB-Hours","endRange":"Inf","description":"AWS Fargate - Ephemeral Storage - US East (N. Virginia)",'
        '"appliesTo":[],"rateCode":"7KPDPTDSCT4J3Z64.JRTCKXETXF.6YS6EN2CT7",'
        '"beginRange":"0","pricePerUnit":{"USD":"0.0001110000"}}},"sku":"7KPDPTDSCT4J3Z64",'
        '"effectiveDate":"2022-11-01T00:00:00Z","offerTermCode":"JRTCKXETXF","termAttributes":{}}}},'
        '"version":"20221121182130","publicationDate":"2022-11-21T18:21:30Z"}',
        '{"product":{"productFamily":"Compute","attributes":{"regionCode":"us-east-1","servicecode":"AmazonECS",'
        '"tenancy":"Shared","usagetype":"USE1-Fargate-vCPU-Hours:perCPU","locationType":"AWS Region",'
        '"location":"US East (N. Virginia)","servicename":"Amazon Elastic Container Service",'
        '"cputype":"perCPU","operation":""},"sku":"8CESGAFWKAJ98PME"},"serviceCode":"AmazonECS",'
        '"terms":{"OnDemand":{"8CESGAFWKAJ98PME.JRTCKXETXF":{"priceDimensions":'
        '{"8CESGAFWKAJ98PME.JRTCKXETXF.6YS6EN2CT7":{"unit":"hours","endRange":"Inf",'
        '"description":"AWS Fargate - vCPU - US East (N.Virginia)","appliesTo":[],'
        '"rateCode":"8CESGAFWKAJ98PME.JRTCKXETXF.6YS6EN2CT7","beginRange":"0",'
        '"pricePerUnit":{"USD":"0.0404800000"}}},"sku":"8CESGAFWKAJ98PME",'
        '"effectiveDate":"2022-11-01T00:00:00Z","offerTermCode":"JRTCKXETXF","termAttributes":{}}}},'
        '"version":"20221121182130","publicationDate":"2022-11-21T18:21:30Z"}',
        '{"product":{"productFamily":"Compute","attributes":{"regionCode":"us-east-1","servicecode":"AmazonECS",'
        '"resource":"per GB per hour","tenancy":"Shared","usagetype":"USE1-Fargate-Windows-GB-Hours",'
        '"locationType":"AWS Region","location":"US East (N. Virginia)",'
        '"servicename":"Amazon Elastic Container Service","memorytype":"perGB",'
        '"operatingSystem":"Windows","operation":""},"sku":"8QDMJPGQCM368Z6X"},'
        '"serviceCode":"AmazonECS","terms":{"OnDemand":{"8QDMJPGQCM368Z6X.JRTCKXETXF":{"priceDimensions":'
        '{"8QDMJPGQCM368Z6X.JRTCKXETXF.6YS6EN2CT7":{"unit":"hours","endRange":"Inf",'
        '"description":"AWS Fargate - Windows - Memory  - US East (N.Virginia)","appliesTo":[],'
        '"rateCode":"8QDMJPGQCM368Z6X.JRTCKXETXF.6YS6EN2CT7","beginRange":"0","pricePerUnit":{"USD":"0.0100500000"}}}'
        ',"sku":"8QDMJPGQCM368Z6X","effectiveDate":"2022-11-01T00:00:00Z",'
        '"offerTermCode":"JRTCKXETXF","termAttributes":{}}}},'
        '"version":"20221121182130","publicationDate":"2022-11-21T18:21:30Z"}',
        '{"product":{"productFamily":"Compute","attributes":'
        '{"regionCode":"us-east-1","servicecode":"AmazonECS",'
        '"resource":"OS License Fee per vCPU per hour","tenancy":"Shared",'
        '"usagetype":"USE1-Fargate-Windows-OS-Hours:perCPU","locationType":'
        '"AWS Region","location":"US East (N. Virginia)",'
        '"servicename":"Amazon Elastic Container Service",'
        '"cputype":"perCPU OS License Fee","operatingSystem":"Windows","operation":""},'
        '"sku":"9D3ZWXRS2VXMZET6"},"serviceCode":"AmazonECS",'
        '"terms":{"OnDemand":{"9D3ZWXRS2VXMZET6.JRTCKXETXF":{"priceDimensions":'
        '{"9D3ZWXRS2VXMZET6.JRTCKXETXF.6YS6EN2CT7":{"unit":"hours","endRange":"Inf","description":'
        '"AWS Fargate - Windows - OS - US East (N.Virginia)","appliesTo":[],'
        '"rateCode":"9D3ZWXRS2VXMZET6.JRTCKXETXF.6YS6EN2CT7","beginRange":"0","pricePerUnit":{"USD":"0.0460000000"}}},'
        '"sku":"9D3ZWXRS2VXMZET6","effectiveDate":"2022-11-01T00:00:00Z","offerTermCode":"JRTCKXETXF",'
        '"termAttributes":{}}}},"version":"20221121182130","publicationDate":"2022-11-21T18:21:30Z"}',
        '{"product":{"productFamily":"Compute Metering","attributes":{"regionCode":"us-east-1",'
        '"servicecode":"AmazonECS","usagetype":"USE1-ECS-EC2-vCPU-Hours","locationType":"AWS Region",'
        '"location":"US East (N. Virginia)","servicename":"Amazon Elastic Container Service"'
        ',"cputype":"perCPU","operation":""},"sku":"DQ8NT47B7YY2CGC5"},"serviceCode":"AmazonECS",'
        '"terms":{"OnDemand":{"DQ8NT47B7YY2CGC5.JRTCKXETXF":'
        '{"priceDimensions":{"DQ8NT47B7YY2CGC5.JRTCKXETXF.6YS6EN2CT7":{"unit":"vCPU-Hours","endRange":"Inf"'
        ',"description":"USD 0.0 per vCPU-Hours for ECS-EC2-vCPU-Hours in US East (N. Virginia)","appliesTo":[]'
        ',"rateCode":"DQ8NT47B7YY2CGC5.JRTCKXETXF.6YS6EN2CT7","beginRange":"0","pricePerUnit":{"USD":"0.0000000000"}}}'
        ',"sku":"DQ8NT47B7YY2CGC5","effectiveDate":"2022-11-01T00:00:00Z",'
        '"offerTermCode":"JRTCKXETXF","termAttributes":{}}}},'
        '"version":"20221121182130","publicationDate":"2022-11-21T18:21:30Z"}',
        '{"product":{"productFamily":"Compute","attributes":{"regionCode":"us-east-1","servicecode":"AmazonECS"'
        ',"tenancy":"Shared","usagetype":"USE1-Fargate-GB-Hours","locationType":"AWS Region",'
        '"location":"US East (N. Virginia)","servicename":"Amazon Elastic Container Service",'
        '"memorytype":"perGB","operation":""},"sku":"PBZNQUSEXZUC34C9"},"serviceCode":"AmazonECS",'
        '"terms":{"OnDemand":{"PBZNQUSEXZUC34C9.JRTCKXETXF":{"priceDimensions":'
        '{"PBZNQUSEXZUC34C9.JRTCKXETXF.6YS6EN2CT7":{"unit":"hours","endRange":"Inf","description":'
        '"AWS Fargate - Memory  - US East (N.Virginia)","appliesTo":[],'
        '"rateCode":"PBZNQUSEXZUC34C9.JRTCKXETXF.6YS6EN2CT7","beginRange":"0","pricePerUnit":'
        '{"USD":"0.0044450000"}}},"sku":"PBZNQUSEXZUC34C9","effectiveDate":"2022-11-01T00:00:00Z",'
        '"offerTermCode":"JRTCKXETXF","termAttributes":{}}}},"version":"20221121182130",'
        '"publicationDate":"2022-11-21T18:21:30Z"}',
        '{"product":{"productFamily":"Compute","attributes":{"regionCode":"us-east-1","servicecode":"AmazonECS"'
        ',"resource":"per vCPU per hour","tenancy":"Shared","usagetype":"USE1-Fargate-Windows-vCPU-Hours:perCPU",'
        '"locationType":"AWS Region","location":"US East (N. Virginia)","servicename":'
        '"Amazon Elastic Container Service","cputype":"perCPU","operatingSystem":"Windows","operation":""}'
        ',"sku":"RF2BUTAD289DREDC"},"serviceCode":"AmazonECS","terms":{"OnDemand":{"RF2BUTAD289DREDC.JRTCKXETXF":'
        '{"priceDimensions":{"RF2BUTAD289DREDC.JRTCKXETXF.6YS6EN2CT7":'
        '{"unit":"hours","endRange":"Inf","description":"AWS Fargate - Windows - vCPU - US East (N.Virginia)",'
        '"appliesTo":[],"rateCode":"RF2BUTAD289DREDC.JRTCKXETXF.6YS6EN2CT7","beginRange":"0"'
        ',"pricePerUnit":{"USD":"0.0914800000"}}},"sku":"RF2BUTAD289DREDC",'
        '"effectiveDate":"2022-11-01T00:00:00Z","offerTermCode":"JRTCKXETXF","termAttributes":{}}}},'
        '"version":"20221121182130","publicationDate":"2022-11-21T18:21:30Z"}',
        '{"product":{"productFamily":"Compute","attributes":{"regionCode":"us-east-1","servicecode":"AmazonECS"'
        ',"resource":"per GB per hour","cpuArchitecture":"ARM","tenancy":"Shared",'
        '"usagetype":"USE1-Fargate-ARM-GB-Hours","locationType":"AWS Region",'
        '"location":"US East (N. Virginia)","servicename":"Amazon Elastic Container Service",'
        '"memorytype":"perGB","operation":""},"sku":"UNH9KPQP7W7C66C9"},'
        '"serviceCode":"AmazonECS","terms":'
        '{"OnDemand":{"UNH9KPQP7W7C66C9.JRTCKXETXF":{"priceDimensions":{"UNH9KPQP7W7C66C9.JRTCKXETXF.6YS6EN2CT7":'
        '{"unit":"hours","endRange":"Inf","description":"AWS Fargate - ARM - Memory - US East (N. Virginia)",'
        '"appliesTo":[],"rateCode":"UNH9KPQP7W7C66C9.JRTCKXETXF.6YS6EN2CT7","beginRange":"0",'
        '"pricePerUnit":{"USD":"0.0035600000"}}},"sku":"UNH9KPQP7W7C66C9","effectiveDate":"2022-11-01T00:00:00Z",'
        '"offerTermCode":"JRTCKXETXF","termAttributes":{}}}},"version":"20221121182130",'
        '"publicationDate":"2022-11-21T18:21:30Z"}',
        '{"product":{"productFamily":"Compute","attributes":{"regionCode":"us-east-1","servicecode":"AmazonECS"'
        ',"usagetype":"USE1-ECS-Anywhere-Instance-hours-WithFree","locationType":"AWS Region",'
        '"location":"US East (N. Virginia)","servicename":"Amazon Elastic Container Service",'
        '"externalInstanceType":"With Free","operation":"AddExternalInstance"},"sku":"VUZADW4HBG7NT6R7"}'
        ',"serviceCode":"AmazonECS","terms":{"OnDemand":{"VUZADW4HBG7NT6R7.JRTCKXETXF":'
        '{"priceDimensions":{"VUZADW4HBG7NT6R7.JRTCKXETXF.2A2Z7VTUXW":{"unit":"hours",'
        '"endRange":"Inf","description":"$0.01025 per hour for ECS-Anywhere-Instance-Hours","appliesTo":[],'
        '"rateCode":"VUZADW4HBG7NT6R7.JRTCKXETXF.2A2Z7VTUXW","beginRange":"2200","pricePerUnit":{"USD":"0.0102500000"}}'
        ',"VUZADW4HBG7NT6R7.JRTCKXETXF.4TES4JTS8Q":{"unit":"hours","endRange":"2200",'
        '"description":"$0 per hour for ECS-Anywhere-Instance-Hours","appliesTo":[],'
        '"rateCode":"VUZADW4HBG7NT6R7.JRTCKXETXF.4TES4JTS8Q","beginRange":"0","pricePerUnit":{"USD":"0.0000000000"}}},'
        '"sku":"VUZADW4HBG7NT6R7","effectiveDate":"2022-11-01T00:00:00Z",'
        '"offerTermCode":"JRTCKXETXF","termAttributes":{}}}},"version":"20221121182130",'
        '"publicationDate":"2022-11-21T18:21:30Z"}',
        '{"product":{"productFamily":"Compute","attributes":{"regionCode":"us-east-1","servicecode":"AmazonECS"'
        ',"usagetype":"USE1-ECS-Anywhere-Instance-hours","locationType":"AWS Region",'
        '"location":"US East (N. Virginia)","servicename":"Amazon Elastic Container Service",'
        '"externalInstanceType":"Default","operation":"AddExternalInstance"},"sku":"WTG8RAG79KP7K3N8"},'
        '"serviceCode":"AmazonECS","terms":{"OnDemand":{"WTG8RAG79KP7K3N8.JRTCKXETXF":'
        '{"priceDimensions":{"WTG8RAG79KP7K3N8.JRTCKXETXF.6YS6EN2CT7":{"unit":"hours","endRange":"Inf"'
        ',"description":"$0.01025 per hour for ECS-Anywhere-Instance-Hours","appliesTo":[],'
        '"rateCode":"WTG8RAG79KP7K3N8.JRTCKXETXF.6YS6EN2CT7","beginRange":"0","pricePerUnit":{"USD":"0.0102500000"}}}'
        ',"sku":"WTG8RAG79KP7K3N8","effectiveDate":"2022-11-01T00:00:00Z","offerTermCode":"JRTCKXETXF",'
        '"termAttributes":{}}}},"version":"20221121182130","publicationDate":"2022-11-21T18:21:30Z"}',
        '{"product":{"productFamily":"Compute","attributes":{"regionCode":"us-east-1","servicecode":"AmazonECS"'
        ',"resource":"per vCPU per hour","cpuArchitecture":"ARM","tenancy":"Shared",'
        '"usagetype":"USE1-Fargate-ARM-vCPU-Hours:perCPU","locationType":"AWS Region",'
        '"location":"US East (N. Virginia)","servicename":"Amazon Elastic Container Service",'
        '"cputype":"perCPU","operation":""},"sku":"XSZATS4VYMDC9CYN"},"serviceCode":'
        '"AmazonECS","terms":{"OnDemand":{"XSZATS4VYMDC9CYN.JRTCKXETXF":'
        '{"priceDimensions":{"XSZATS4VYMDC9CYN.JRTCKXETXF.6YS6EN2CT7":{"unit":"hours","endRange":"Inf",'
        '"description":"AWS Fargate - ARM - vCPU - US East (N. Virginia)","appliesTo":[],'
        '"rateCode":"XSZATS4VYMDC9CYN.JRTCKXETXF.6YS6EN2CT7","beginRange":"0",'
        '"pricePerUnit":{"USD":"0.0323800000"}}},"sku":"XSZATS4VYMDC9CYN","effectiveDate":"2022-11-01T00:00:00Z",'
        '"offerTermCode":"JRTCKXETXF","termAttributes":{}}}},"version":"20221121182130",'
        '"publicationDate":"2022-11-21T18:21:30Z"}',
    ],
    "ResponseMetadata": {
        "RequestId": "beb3ee49-a366-46ab-bf9a-951646345c00",
        "HTTPStatusCode": 200,
        "HTTPHeaders": {
            "x-amzn-requestid": "beb3ee49-a366-46ab-bf9a-951646345c00",
            "content-type": "application/x-amz-json-1.1",
            "content-length": "12725",
            "date": "Fri, 25 Nov 2022 10:11:08 GMT",
        },
        "RetryAttempts": 0,
    },
}

TASK_DEFINITION_MOCK = {
    "taskDefinition": {
        "taskDefinitionArn": "arn:aws:ecs:us-east-1:121169888995:task-definition/prowler:5",
        "containerDefinitions": [
            {
                "name": "default",
                "image": "121169888995.dkr.ecr.us-east-1.amazonaws.com/prowler:latest",
                "cpu": 0,
                "portMappings": [],
                "essential": True,
                "environment": [],
                "mountPoints": [],
                "volumesFrom": [],
                "secrets": [],
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": "/ecs/prowler-container",
                        "awslogs-region": "us-east-1",
                        "awslogs-stream-prefix": "ecs",
                    },
                    "secretOptions": [],
                },
            }
        ],
        "family": "prowler",
        "executionRoleArn": "arn:aws:iam::121169888995:role/ecs_task_role",
        "networkMode": "awsvpc",
        "revision": 5,
        "volumes": [],
        "status": "ACTIVE",
        "requiresAttributes": [
            {"name": "com.amazonaws.ecs.capability.logging-driver.awslogs"},
            {"name": "ecs.capability.execution-role-awslogs"},
            {"name": "com.amazonaws.ecs.capability.ecr-auth"},
            {"name": "com.amazonaws.ecs.capability.docker-remote-api.1.19"},
            {"name": "ecs.capability.execution-role-ecr-pull"},
            {"name": "com.amazonaws.ecs.capability.docker-remote-api.1.18"},
            {"name": "ecs.capability.task-eni"},
        ],
        "placementConstraints": [],
        "compatibilities": ["EC2", "FARGATE"],
        "requiresCompatibilities": ["FARGATE"],
        "cpu": "512",
        "memory": "2048",
        "registeredAt": "2022-11-22T15:32:49.644000+02:00",
        "registeredBy": "arn:aws:sts::121169888995:assumed-role/AWSServiceRoleForBatch/aws-batch",
    },
    "tags": [],
}

MOCK_ECS_EVENT_FAILED_TO_START = {
    "version": "0",
    "id": "27888c40-438d-3fea-1f37-d77b65098c9a",
    "detail-type": "ECS Task State Change",
    "source": "aws.ecs",
    "account": "899025839375",
    "event_time": "2022-12-07T12:06:52Z",
    "region": "us-east-1",
    "resources": [
        "arn:aws:ecs:us-east-1:899025839375:task/AWSBatch-fargate-batch-compute-f"
    ],
    "detail": {
        "attachments": [
            {
                "id": "08988a29-360d-4188-8aef-b839d2fdebf1",
                "type": "eni",
                "status": "DELETED",
                "details": [
                    {"name": "subnetId", "value": "subnet-0ad6704ed7343869e"},
                    {"name": "networkInterfaceId", "value": "eni-0bda457731e44c065"},
                    {"name": "macAddress", "value": "02:de:06:f3:14:89"},
                    {"name": "privateIPv4Address", "value": "10.0.0.218"},
                ],
            }
        ],
        "attributes": [{"name": "ecs.cpu-architecture", "value": "x86_64"}],
        "availabilityZone": "us-east-1a",
        "capacityProviderName": "FARGATE",
        "clusterArn": "arn:aws:ecs:us-east-1:899025839375:cluste",
        "connectivity": "CONNECTED",
        "connectivityAt": "2022-12-07T12:06:27.852Z",
        "containers": [
            {
                "containerArn": "arn:aws:ecs:us-east-1:899025839375:contain",
                "lastStatus": "STOPPED",
                "name": "default",
                "image": "899025839375.dkr.ecr.us-east-1.amazonaws.com/prowler:latest",
                "taskArn": "arn:aws:ecs:us-east-1:899025839375:task/AWSBatch-fargate-batch-",
                "networkInterfaces": [
                    {
                        "attachmentId": "08988a29-360d-4188-8aef-b839d2fdebf1",
                        "privateIpv4Address": "10.0.0.218",
                    }
                ],
                "cpu": "0",
            }
        ],
        "cpu": "512",
        "createdAt": "2022-12-07T12:02:48.873Z",
        "desiredStatus": "STOPPED",
        "enableExecuteCommand": False,
        "ephemeralStorage": {"sizeInGiB": 20},
        "group": "family:prowler",
        "launchType": "FARGATE",
        "lastStatus": "STOPPED",
        "memory": "2048",
        "overrides": {
            "containerOverrides": [
                {
                    "environment": [
                        {
                            "name": "AWS_BATCH_JOB_ID",
                            "value": "0268d907-34a3-43e3-9905-f3d3a20f3842",
                        },
                        {"name": "AWS_BATCH_JQ_NAME", "value": "fargate-tasks-queue"},
                        {"name": "regions", "value": "eu-central-1"},
                        {"name": "AWS_BATCH_JOB_ATTEMPT", "value": "1"},
                        {
                            "name": "AWS_SECRET_ACCESS_KEY",
                            "value": "NMk2QFUb5M2IyZEhdj+FKyun3muNLMtDuW3r9bZe",
                        },
                        {
                            "name": "EVENT",
                            "value": '{"job": "runtime-misconfig-detection-ssm", "workflow": '
                            '"runtime-misconfig-detection-ssm", '
                            '"run_id": "7b14dd0f-311b-4a40-acac-d04304036f79", '
                            '"payload": {"tenant_id": "a748be55-1af1-44da-9584-b018d1016b46", "vendor": '
                            '"aws", "account_id": "403017019398", "account_name": "Seemplicity Staging",'
                            ' "workflow_suite_id": "416cadec-f8b8-4305-bd7b-39edb9be73e1",'
                            ' "jit_event_id": "416cadec-f8b8-4305-bd7b-39edb9be73e1",'
                            ' "execution_id": "7b14dd0f-311b-4a40-acac-d04304036f79", '
                            '"callback_urls": {"workflow": "https://api.jit.io/execution", "execution": '
                            '"https://api.jit.io/execution", '
                            '"logs": "https://api.jit.io/execution/jit-event/416cadec-f8b8-4305-bd7", '
                            '"presigned_logs_upload_url": "https://jit-execution-logs-prod.s3.amazonaws", '
                            '"findings": "https://api.jit.io/finding/5-a2d6-7213bbb8687e/new", '
                            '"presigned_findings_upload_url": "https", '
                            '"ignores": "https://api.jit.io/", '
                            '"actions": null}, '
                            '"callback_token": "..-----", '
                            '"asset_type": "aws_account", '
                            '"asset_id": "07c186f8-b900-41a5-a2d6-7213bbb8687e", '
                            '"inputs": {"args": "account_ids=\\"$AWS_ACCOUNT_IDS\\"", '
                            '"checks": "extra7141,extra7140,extra7127"},'
                            ' "use_execution_engine": true, '
                            '"control_timeout_seconds": 7200, "job_runner": "jit", '
                            '"plan_slug": "jit-plan", "plan_item_slug": '
                            '"item-runtime-misconfiguration-detection",'
                            ' "step_name": "runtime-misconfig-detection-ssm"}}',
                        },
                        {"name": "checks", "value": "extra7141,extra7140,extra7127"},
                        {"name": "REGION_NAME", "value": "us-east-1"},
                        {"name": "AWS_BATCH_CE_NAME", "value": "fargate-batch-compute"},
                    ],
                    "name": "default",
                }
            ],
            "cpu": "512",
            "memory": "2048",
        },
        "platformVersion": "1.4.0",
        "stoppingAt": "2022-12-07T12:05:51.863Z",
        "stoppedAt": "2022-12-07T12:06:40.232Z",
        "stoppedReason": "Timeout waiting for network interface provisioning to complete.",
        "stopCode": "TaskFailedToStart",
        "taskArn": "arn:aws:ecs:us-east-1:899025839375:task/AWSBatch-fargate-batch-compute-fde45500",
        "taskDefinitionArn": "arn:aws:ecs:us-east-1:899025839375:task-definition/prowler:3",
        "updatedAt": "2022-12-07T12:06:52.827Z",
        "version": 4,
    },
}
