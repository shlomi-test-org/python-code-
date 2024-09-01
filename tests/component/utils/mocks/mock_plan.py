# flake8: noqa
MOCK_PLAN = {
    "items": {
        "item-branch-protection-scm": {
            "item_template": {
                "slug": "item-branch-protection-scm",
                "name": "Verify that Github Branch Protection is properly configured",
                "type": "plan_item",
                "content": "namespace: jit.third_party_app\nname: Verify that Github Branch Protection is properly "
                           "configured\ndescription: |\n  Branch protection is an important GitHub feature that "
                           "allows you to "
                "protect specific git branches from unauthorized modifications.\n  By setting branch protection you "
                "can define whether collaborators can delete or force push to the branch and set requirements for any "
                "pushes to that branch.\n  For example, requirements like minimum number of approvers for PRs and "
                "list of mandatory status checks.\nsummary: |\n  Ensure you have Branch Protection enabled for all "
                "repos with the desired requirements.\nworkflows:\n  - uses: "
                "jitsecurity-controls/jit-plans/workflows/workflow-branch-protection-github-checker@latest\n    "
                "default: True\ntags:\n  layer: third_party_app\n  risk_category: access_control\n",
                "parsed_content": {
                    "namespace": "jit.third_party_app",
                    "name": "Verify that Github Branch Protection is properly configured",
                    "summary": "Ensure you have Branch Protection enabled for all repos with the desired requirements.\n",
                    "description": "Branch protection is an important GitHub feature that allows you to protect specific git branches from unauthorized modifications.\nBy setting branch protection you can define whether collaborators can delete or force push to the branch and set requirements for any pushes to that branch.\nFor example, requirements like minimum number of approvers for PRs and list of mandatory status checks.\n",
                    "workflows": [
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-branch-protection-github-checker@latest",
                            "default": True
                        }
                    ],
                    "tags": {
                        "layer": "third_party_app",
                        "risk_category": "access_control"
                    }
                },
                "plan_template_slugs": [
                    "plan-mvs-for-cloud-app"
                ],
                "asset_types": [
                    "repo"
                ]
            },
            "workflow_templates": [
                {
                    "slug": "workflow-branch-protection-github-checker",
                    "name": "Branch Protection Checker on Github Workflow",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  branch-protection-github-checker:\n    asset_type: repo\n    default: True\n    runner:\n      setup:\n        auth_type: scm_token\n        timeout_minutes: 10\n      type: jit\n    steps:\n    - name: Run Branch Protection checker\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-github-branch-protection-control\n        security_tool: Branch Protection Checker\n      uses: 899025839375.dkr.ecr.us-east-1.amazonaws.com/github-branch-protection:latest\n      with:\n        args: --organization-name ${{ context.asset.owner }} --repo-name ${{ context.asset.asset_name\n          }} --centralized-repo-asset-name ${{ context.installation.centralized_repo_asset.asset_name\n          }}\n        env:\n          GITHUB_TOKEN: ${{ context.auth.config.github_token }}\n          JIT_CONFIG_CONTENT: ${{ context.config }}\nname: Branch Protection Checker on Github Workflow\ntrigger:\n  True:\n  - item_activated\n  - resource_added\n  - schedule(\"daily\")\n  - manual_execution\n",
                    "depends_on": [

                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "repo"
                    ],
                    "parsed_content": {
                        "name": "Branch Protection Checker on Github Workflow",
                        "jobs": {
                            "branch-protection-github-checker": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "jit",
                                    "setup": {
                                        "auth_type": "scm_token",
                                        "timeout_minutes": 10,
                                    }
                                },
                                "steps": [
                                    {
                                        "name": "Run Branch Protection checker",
                                        "with": {
                                            "args": "--organization-name ${{ context.asset.owner }} --repo-name ${{ context.asset.asset_name }} --centralized-repo-asset-name ${{ context.installation.centralized_repo_asset.asset_name }}",
                                            "env": {
                                                "GITHUB_TOKEN": "${{ context.auth.config.scm_token }}",
                                                "JIT_CONFIG_CONTENT": "${{ context.config }}"
                                            }
                                        },
                                        "uses": "899025839375.dkr.ecr.us-east-1.amazonaws.com/github-branch-protection:latest",
                                        "tags": {
                                            "security_tool": "Branch Protection Checker",
                                            "links": {
                                                "github": "https://github.com/jitsecurity-controls/jit-github-branch-protection-control"
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                        "trigger": {
                            "True": [
                                "item_activated",
                                "resource_added",
                                "schedule(\"daily\")"
                            ]
                        }
                    }
                }
            ]
        },
        "item-cloud-security-posture-management": {
            "item_template": {
                "slug": "item-cloud-security-posture-management",
                "name": "Scan your AWS environment for enhanced security posture",
                "type": "plan_item",
                "content": "namespace: jit.infrastructure\nname: Scan your AWS environment for enhanced security posture\ndescription: |\n  Cloud security posture management (CSPM) identifies and remediates risk by automating visibility, uninterrupted monitoring,\n  threat detection, and remediation workflows to search for misconfigurations across diverse cloud environments/infrastructure\nsummary: |\n  Jit will import the results of the Cloud Security Posture Management into the Jit platform.\nworkflows:\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-cloud-security-posture-aws-checker@latest\n    default: True\ntags:\n  layer: infrastructure\n  risk_category: misconfiguration\n",
                "parsed_content": {
                    "namespace": "jit.infrastructure",
                    "name": "Scan your AWS environment for enhanced security posture",
                    "summary": "Jit will import the results of the Cloud Security Posture Management into the Jit platform.\n",
                    "description": "Cloud security posture management (CSPM) identifies and remediates risk by automating visibility, uninterrupted monitoring,\nthreat detection, and remediation workflows to search for misconfigurations across diverse cloud environments/infrastructure\n",
                    "workflows": [
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-cloud-security-posture-aws-checker@latest",
                            "default": True
                        }
                    ],
                    "tags": {
                        "layer": "infrastructure",
                        "risk_category": "misconfiguration"
                    }
                },
                "plan_template_slugs": [
                    "plan-mvs-for-cloud-app"
                ],
                "asset_types": [
                    "aws_account"
                ]
            },
            "workflow_templates": [
                {
                    "slug": "workflow-cloud-security-posture-aws-checker",
                    "name": "AWS Security Hub Workflow",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  aws-security-hub:\n    asset_type: aws_account\n    default: True\n    runner:\n      setup:\n        auth_type: aws_iam_role\n      type: jit\n    steps:\n    - name: Run AWS Security Hub\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-aws-security-hub-control\n        security_tool: AWS Security Hub\n      uses: 899025839375.dkr.ecr.us-east-1.amazonaws.com/aws-security-hub:latest\n      with:\n        args: \\'--minimal-severity-normalized 70 --workflow-state-to-filter SUPPRESSED\n          RESOLVED\n\n          \\'\n        env:\n          AWS_ACCESS_KEY_ID: ${{ context.auth.config.aws_access_key_id }}\n          AWS_REGION_NAME: ${{ context.auth.config.region_name }}\n          AWS_SECRET_ACCESS_KEY: ${{ context.auth.config.aws_secret_access_key }}\n          AWS_SESSION_TOKEN: ${{ context.auth.config.aws_session_token }}\nname: AWS Security Hub Workflow\ntrigger:\n  True:\n  - item_activated\n  - resource_added\n  - schedule(\"daily\")\n  - manual_execution\n",
                    "depends_on": [

                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "aws_account"
                    ],
                    "parsed_content": {
                        "name": "AWS Security Hub Workflow",
                        "jobs": {
                            "aws-security-hub": {
                                "asset_type": "aws_account",
                                "default": True,
                                "runner": {
                                    "type": "jit",
                                    "setup": {
                                        "auth_type": "aws_iam_role"
                                    }
                                },
                                "steps": [
                                    {
                                        "name": "Run AWS Security Hub",
                                        "with": {
                                            "args": "--minimal-severity-normalized 70 --workflow-state-to-filter SUPPRESSED RESOLVED\n",
                                            "env": {
                                                "AWS_SESSION_TOKEN": "${{ context.auth.config.aws_session_token }}",
                                                "AWS_REGION_NAME": "${{ context.auth.config.region_name }}",
                                                "AWS_ACCESS_KEY_ID": "${{ context.auth.config.aws_access_key_id }}",
                                                "AWS_SECRET_ACCESS_KEY": "${{ context.auth.config.aws_secret_access_key }}"
                                            }
                                        },
                                        "uses": "899025839375.dkr.ecr.us-east-1.amazonaws.com/aws-security-hub:latest",
                                        "tags": {
                                            "security_tool": "AWS Security Hub",
                                            "links": {
                                                "github": "https://github.com/jitsecurity-controls/jit-aws-security-hub-control"
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                        "trigger": {
                            "True": [
                                "item_activated",
                                "resource_added",
                                "schedule(\"daily\")"
                            ]
                        }
                    }
                }
            ]
        },
        "item-code-vulnerability": {
            "item_template": {
                "slug": "item-code-vulnerability",
                "name": "Scan your code for vulnerabilities (SAST)",
                "type": "plan_item",
                "content": "namespace: jit.code\nname: Scan your code for vulnerabilities (SAST)\ndescription: |\n  Static code analysis tools can discover vulnerabilities inside your code before they make their way to production.\nsummary: |\n  Upon activation, Jit will launch an initial scan on all your code files. Jit will then continuously scan changes, anytime a Pull Request is created or updated.\nworkflows:\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-sast@latest\n    default: True\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-remediation-pr@latest\n    default: True\ntags:\n  layer: code\n  risk_category: code_vulnerability\n  compliance:soc2: CC7.1\n  compliance:iso-27001: A.12.6.1\n",
                "parsed_content": {
                    "namespace": "jit.code",
                    "name": "Scan your code for vulnerabilities (SAST)",
                    "summary": "Upon activation, Jit will launch an initial scan on all your code files. Jit will then continuously scan changes, anytime a Pull Request is created or updated.\n",
                    "description": "Static code analysis tools can discover vulnerabilities inside your code before they make their way to production.\n",
                    "workflows": [
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-sast@latest",
                            "default": True
                        },
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-remediation-pr@latest",
                            "default": True
                        }
                    ],
                    "tags": {
                        "compliance:soc2": "CC7.1",
                        "compliance:iso-27001": "A.12.6.1",
                        "risk_category": "code_vulnerability",
                        "layer": "code"
                    }
                },
                "plan_template_slugs": [
                    "plan-iso-27001",
                    "plan-soc2",
                    "plan-mvs-for-cloud-app"
                ],
                "asset_types": [
                    "repo"
                ]
            },
            "workflow_templates": [
                {
                    "slug": "workflow-remediation-pr",
                    "name": "Remediation Pull Request Workflow",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  remediation-pr:\n    asset_type: repo\n    default: True\n    runner:\n      setup:\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run Jit Remediation\n      tags:\n        is_hidden: True\n        links: []\n        security_tool: Jit-remediation\n        workflow_type: remediation\n      uses: ghcr.io/jitsecurity-controls/open-remediation-pr-alpine:latest\n      with:\n        args: --github-token ${{fromJSON(github.event.inputs.client_payload).payload.github_token}}\n          --fix-pr-config ${{fromJSON(github.event.inputs.client_payload).payload.fix_pr_config}}\n          --output-file \\$REPORT_FILE\n        output_file: /opt/code/jit-report/results.json\nname: Remediation Pull Request Workflow\ntrigger:\n  True:\n  - open_fix_pull_request\n",
                    "depends_on": [

                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "repo"
                    ],
                    "parsed_content": {
                        "name": "Remediation Pull Request Workflow",
                        "jobs": {
                            "remediation-pr": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "timeout_minutes": 10,
                                    }
                                },
                                "steps": [
                                    {
                                        "name": "Run Jit Remediation",
                                        "with": {
                                            "args": "--github-token ${{fromJSON(github.event.inputs.client_payload).payload.github_token}} --fix-pr-config ${{fromJSON(github.event.inputs.client_payload).payload.fix_pr_config}} --output-file \\$REPORT_FILE",
                                            "output_file": "/opt/code/jit-report/results.json"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/open-remediation-pr-alpine:latest",
                                        "tags": {
                                            "is_hidden": True,
                                            "security_tool": "Jit-remediation",
                                            "links": [

                                            ],
                                            "workflow_type": "remediation"
                                        }
                                    }
                                ]
                            }
                        },
                        "trigger": {
                            "True": [
                                "open_fix_pull_request"
                            ]
                        }
                    }
                },
                {
                    "slug": "workflow-sast",
                    "name": "SAST Workflow",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  static-code-analysis-csharp:\n    asset_type: repo\n    default: True\n    if:\n      languages:\n      - csharp\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run semgrep csharp\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control\n          security_tool: https://github.com/returntocorp/semgrep\n        security_tool: Semgrep\n      uses: ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest\n      with:\n        args: --json --config=/semgrep-csharp-config.yml --metrics=off --severity=ERROR\n          \\${WORK_DIR:-.}\n    tags:\n      languages:\n      - csharp\n  static-code-analysis-go:\n    asset_type: repo\n    default: True\n    if:\n      languages:\n      - go\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run Go\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-golang-code-scanning-control\n          security_tool: https://github.com/securego/gosec\n        security_tool: Gosec\n      uses: ghcr.io/jitsecurity-controls/control-gosec-alpine:latest\n      with:\n        args: -fmt=json -severity=high \\${WORK_DIR:-.}/...\n    tags:\n      languages:\n      - go\n  static-code-analysis-java:\n    asset_type: repo\n    if:\n      languages:\n      - java\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run semgrep java\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control\n          security_tool: https://github.com/returntocorp/semgrep\n        security_tool: Semgrep\n      uses: ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest\n      with:\n        args: --json --config=/semgrep-java-config.yml --metrics=off --severity=ERROR\n          \\${WORK_DIR:-.}\n    tags:\n      languages:\n      - java\n  static-code-analysis-js:\n    asset_type: repo\n    default: True\n    if:\n      languages:\n      - javascript\n      - typescript\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run semgrep javascript and typescript\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control\n          security_tool: https://github.com/returntocorp/semgrep\n        security_tool: Semgrep\n      uses: ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest\n      with:\n        args: --json --config=/semgrep-ts-config.yml --metrics=off --severity=ERROR\n          \\${WORK_DIR:-.}\n    tags:\n      languages:\n      - javascript\n      - typescript\n      - JS\n      - TS\n  static-code-analysis-kotlin:\n    asset_type: repo\n    default: True\n    if:\n      languages:\n      - kotlin\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run semgrep kotlin\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control\n          security_tool: https://github.com/returntocorp/semgrep\n        security_tool: Semgrep\n      uses: ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest\n      with:\n        args: --json --config=/semgrep-kotlin-config.yml --metrics=off --severity=ERROR\n          \\${WORK_DIR:-.}\n    tags:\n      languages:\n      - kotlin\n  static-code-analysis-python-semgrep:\n    asset_type: repo\n    default: True\n    if:\n      languages:\n      - python\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run semgrep python\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control\n          security_tool: https://github.com/returntocorp/semgrep\n        security_tool: Semgrep\n      uses: ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest\n      with:\n        args: --json --config=/semgrep-python-config.yml --metrics=off --severity=ERROR\n          \\${WORK_DIR:-.}\n    tags:\n      languages:\n      - python\n  static-code-analysis-rust:\n    asset_type: repo\n    default: True\n    if:\n      languages:\n      - rust\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run semgrep rust\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control\n          security_tool: https://github.com/returntocorp/semgrep\n        security_tool: Semgrep\n      uses: ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest\n      with:\n        args: --json --config=/semgrep-rust-config.yml --metrics=off --severity=ERROR\n          \\${WORK_DIR:-.}\n    tags:\n      languages:\n      - rust\n  static-code-analysis-scala:\n    asset_type: repo\n    if:\n      languages:\n      - scala\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run semgrep scala\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control\n          security_tool: https://github.com/returntocorp/semgrep\n        security_tool: Semgrep\n      uses: ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest\n      with:\n        args: --json --config=/semgrep-scala-config.yml --metrics=off --severity=ERROR\n          \\${WORK_DIR:-.}\n    tags:\n      languages:\n      - scala\n  static-code-analysis-swift:\n    asset_type: repo\n    default: True\n    if:\n      languages:\n      - swift\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run semgrep swift\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control\n          security_tool: https://github.com/returntocorp/semgrep\n        security_tool: Semgrep\n      uses: ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest\n      with:\n        args: --json --config=/semgrep-swift-config.yml --metrics=off --severity=ERROR\n          \\${WORK_DIR:-.}\n    tags:\n      languages:\n      - swift\nname: SAST Workflow\ntrigger:\n  True:\n  - item_activated\n  - resource_added\n  - pull_request_created\n  - pull_request_updated\n  - merge_default_branch\n  - manual_execution\n  depends_on:\n  - workflow-enrichment-code\n",
                    "depends_on": [
                        "workflow-enrichment-code"
                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "repo",
                        "repo",
                        "repo",
                        "repo",
                        "repo",
                        "repo",
                        "repo",
                        "repo",
                        "repo",
                        "repo"
                    ],
                    "parsed_content": {
                        "name": "SAST Workflow",
                        "jobs": {
                            "static-code-analysis-csharp": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10,
                                    }
                                },
                                "if": {
                                    "languages": [
                                        "csharp"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run semgrep csharp",
                                        "with": {
                                            "args": "--json --config=/semgrep-csharp-config.yml --metrics=off --severity=ERROR \\${WORK_DIR:-.}"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest",
                                        "tags": {
                                            "security_tool": "Semgrep",
                                            "links": {
                                                "security_tool": "https://github.com/returntocorp/semgrep",
                                                "github": "https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "csharp"
                                    ]
                                }
                            },
                            "static-code-analysis-go": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10
                                    }
                                },
                                "if": {
                                    "languages": [
                                        "go"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run Go",
                                        "with": {
                                            "args": "-fmt=json -severity=high \\${WORK_DIR:-.}/..."
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-gosec-alpine:latest",
                                        "tags": {
                                            "security_tool": "Gosec",
                                            "links": {
                                                "security_tool": "https://github.com/securego/gosec",
                                                "github": "https://github.com/jitsecurity-controls/jit-golang-code-scanning-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "go"
                                    ]
                                }
                            },
                            "static-code-analysis-js": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10
                                    }
                                },
                                "if": {
                                    "languages": [
                                        "javascript",
                                        "typescript"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run semgrep javascript and typescript",
                                        "with": {
                                            "args": "--json --config=/semgrep-ts-config.yml --metrics=off --severity=ERROR \\${WORK_DIR:-.}"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest",
                                        "tags": {
                                            "security_tool": "Semgrep",
                                            "links": {
                                                "security_tool": "https://github.com/returntocorp/semgrep",
                                                "github": "https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "javascript",
                                        "typescript",
                                        "JS",
                                        "TS"
                                    ]
                                }
                            },
                            "static-code-analysis-rust": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10
                                    }
                                },
                                "if": {
                                    "languages": [
                                        "rust"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run semgrep rust",
                                        "with": {
                                            "args": "--json --config=/semgrep-rust-config.yml --metrics=off --severity=ERROR \\${WORK_DIR:-.}"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest",
                                        "tags": {
                                            "security_tool": "Semgrep",
                                            "links": {
                                                "security_tool": "https://github.com/returntocorp/semgrep",
                                                "github": "https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "rust"
                                    ]
                                }
                            },
                            "static-code-analysis-python-semgrep": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10
                                    }
                                },
                                "if": {
                                    "languages": [
                                        "python"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run semgrep python",
                                        "with": {
                                            "args": "--json --config=/semgrep-python-config.yml --metrics=off --severity=ERROR \\${WORK_DIR:-.}"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest",
                                        "tags": {
                                            "security_tool": "Semgrep",
                                            "links": {
                                                "security_tool": "https://github.com/returntocorp/semgrep",
                                                "github": "https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "python"
                                    ]
                                }
                            },
                            "static-code-analysis-scala": {
                                "asset_type": "repo",
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10
                                    }
                                },
                                "if": {
                                    "languages": [
                                        "scala"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run semgrep scala",
                                        "with": {
                                            "args": "--json --config=/semgrep-scala-config.yml --metrics=off --severity=ERROR \\${WORK_DIR:-.}"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest",
                                        "tags": {
                                            "security_tool": "Semgrep",
                                            "links": {
                                                "security_tool": "https://github.com/returntocorp/semgrep",
                                                "github": "https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "scala"
                                    ]
                                }
                            },
                            "static-code-analysis-kotlin": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10
                                    }
                                },
                                "if": {
                                    "languages": [
                                        "kotlin"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run semgrep kotlin",
                                        "with": {
                                            "args": "--json --config=/semgrep-kotlin-config.yml --metrics=off --severity=ERROR \\${WORK_DIR:-.}"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest",
                                        "tags": {
                                            "security_tool": "Semgrep",
                                            "links": {
                                                "security_tool": "https://github.com/returntocorp/semgrep",
                                                "github": "https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "kotlin"
                                    ]
                                }
                            },
                            "static-code-analysis-swift": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10
                                    }
                                },
                                "if": {
                                    "languages": [
                                        "swift"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run semgrep swift",
                                        "with": {
                                            "args": "--json --config=/semgrep-swift-config.yml --metrics=off --severity=ERROR \\${WORK_DIR:-.}"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest",
                                        "tags": {
                                            "security_tool": "Semgrep",
                                            "links": {
                                                "security_tool": "https://github.com/returntocorp/semgrep",
                                                "github": "https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "swift"
                                    ]
                                }
                            },
                            "static-code-analysis-java": {
                                "asset_type": "repo",
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10
                                    }
                                },
                                "if": {
                                    "languages": [
                                        "java"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run semgrep java",
                                        "with": {
                                            "args": "--json --config=/semgrep-java-config.yml --metrics=off --severity=ERROR \\${WORK_DIR:-.}"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest",
                                        "tags": {
                                            "security_tool": "Semgrep",
                                            "links": {
                                                "security_tool": "https://github.com/returntocorp/semgrep",
                                                "github": "https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "java"
                                    ]
                                }
                            }
                        },
                        "trigger": {
                            "True": [
                                "item_activated",
                                "resource_added",
                                "pull_request_created",
                                "pull_request_updated",
                                "merge_default_branch",
                                "manual_execution"
                            ],
                            "depends_on": [
                                "workflow-enrichment-code"
                            ]
                        }
                    }
                }
            ]
        },
        "item-container-scan": {
            "item_template": {
                "slug": "item-container-scan",
                "name": "Scan your Dockerfiles for vulnerabilities",
                "type": "plan_item",
                "content": "namespace: jit.infrastructure\nname: Scan your Dockerfiles for vulnerabilities\ndescription: |\n  Scanning Dockerfiles will help you catch security vulnerabilities earlier in the development process and before deployment.\nsummary: |\n  Upon activation, Jit will launch an initial scan on all your Dockerfiles. Jit will then continuously scan changes in Dockerfiles, anytime a Pull Request is created or updated.\nworkflows:\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-docker-scan@latest\n    default: True\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-remediation-pr@latest\n    default: True\ntags:\n  layer: infrastructure\n  risk_category: supply_chain_attack\n",
                "parsed_content": {
                    "namespace": "jit.infrastructure",
                    "name": "Scan your Dockerfiles for vulnerabilities",
                    "summary": "Upon activation, Jit will launch an initial scan on all your Dockerfiles. Jit will then continuously scan changes in Dockerfiles, anytime a Pull Request is created or updated.\n",
                    "description": "Scanning Dockerfiles will help you catch security vulnerabilities earlier in the development process and before deployment.\n",
                    "workflows": [
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-docker-scan@latest",
                            "default": True
                        },
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-remediation-pr@latest",
                            "default": True
                        }
                    ],
                    "tags": {
                        "layer": "infrastructure",
                        "risk_category": "supply_chain_attack"
                    }
                },
                "plan_template_slugs": [
                    "plan-mvs-for-cloud-app"
                ],
                "asset_types": [
                    "repo"
                ]
            },
            "workflow_templates": [
                {
                    "slug": "workflow-docker-scan",
                    "name": "Docker Scan Workflow",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  docker-scan:\n    asset_type: repo\n    default: True\n    if:\n      frameworks:\n      - docker\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run trivy\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-trivy-dockerfile-scanner-control\n          security_tool: https://github.com/aquasecurity/trivy\n        security_tool: Trivy\n      uses: ghcr.io/jitsecurity-controls/control-trivy-alpine:latest\n      with:\n        args: --quiet config --severity HIGH,CRITICAL -f json --ignorefile /opt/.trivyignore\n          \\${WORK_DIR:-.}\n    tags:\n      languages:\n      - docker\nname: Docker Scan Workflow\ntrigger:\n  True:\n  - item_activated\n  - resource_added\n  - pull_request_created\n  - pull_request_updated\n  - merge_default_branch\n  depends_on:\n  - workflow-enrichment-code\n  - manual_execution\n",
                    "depends_on": [
                        "workflow-enrichment-code"
                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "repo"
                    ],
                    "parsed_content": {
                        "name": "Docker Scan Workflow",
                        "jobs": {
                            "docker-scan": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10,
                                    }
                                },
                                "if": {
                                    "frameworks": [
                                        "docker"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run trivy",
                                        "with": {
                                            "args": "--quiet config --severity HIGH,CRITICAL -f json --ignorefile /opt/.trivyignore \\${WORK_DIR:-.}"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-trivy-alpine:latest",
                                        "tags": {
                                            "security_tool": "Trivy",
                                            "links": {
                                                "security_tool": "https://github.com/aquasecurity/trivy",
                                                "github": "https://github.com/jitsecurity-controls/jit-trivy-dockerfile-scanner-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "docker"
                                    ]
                                }
                            }
                        },
                        "trigger": {
                            "True": [
                                "item_activated",
                                "resource_added",
                                "pull_request_created",
                                "pull_request_updated",
                                "merge_default_branch"
                            ],
                            "depends_on": [
                                "workflow-enrichment-code"
                            ]
                        }
                    }
                },
                {
                    "slug": "workflow-remediation-pr",
                    "name": "Remediation Pull Request Workflow",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  remediation-pr:\n    asset_type: repo\n    default: True\n    runner:\n      setup:\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run Jit Remediation\n      tags:\n        is_hidden: True\n        links: []\n        security_tool: Jit-remediation\n        workflow_type: remediation\n      uses: ghcr.io/jitsecurity-controls/open-remediation-pr-alpine:latest\n      with:\n        args: --github-token ${{fromJSON(github.event.inputs.client_payload).payload.github_token}}\n          --fix-pr-config ${{fromJSON(github.event.inputs.client_payload).payload.fix_pr_config}}\n          --output-file \\$REPORT_FILE\n        output_file: /opt/code/jit-report/results.json\nname: Remediation Pull Request Workflow\ntrigger:\n  True:\n  - open_fix_pull_request\n",
                    "depends_on": [

                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "repo"
                    ],
                    "parsed_content": {
                        "name": "Remediation Pull Request Workflow",
                        "jobs": {
                            "remediation-pr": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "timeout_minutes": 10
                                    }
                                },
                                "steps": [
                                    {
                                        "name": "Run Jit Remediation",
                                        "with": {
                                            "args": "--github-token ${{fromJSON(github.event.inputs.client_payload).payload.github_token}} --fix-pr-config ${{fromJSON(github.event.inputs.client_payload).payload.fix_pr_config}} --output-file \\$REPORT_FILE",
                                            "output_file": "/opt/code/jit-report/results.json"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/open-remediation-pr-alpine:latest",
                                        "tags": {
                                            "is_hidden": True,
                                            "security_tool": "Jit-remediation",
                                            "links": [

                                            ],
                                            "workflow_type": "remediation"
                                        }
                                    }
                                ]
                            }
                        },
                        "trigger": {
                            "True": [
                                "open_fix_pull_request"
                            ]
                        }
                    }
                }
            ]
        },
        "item-dependency-check": {
            "item_template": {
                "slug": "item-dependency-check",
                "name": "Scan your code dependencies for vulnerabilities (SCA)",
                "type": "plan_item",
                "content": "namespace: jit.code\nname: Scan your code dependencies for vulnerabilities (SCA)\ndescription: |\n  Code dependencies should be scanned for vulnerabilities, as vulnerable dependencies can cause a range of problems\n  for your project or the people who use it.\nsummary: |\n  Integrate SCA tool into CI/CD so it automatically runs for every new PR.\nworkflows:\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-sca@latest\n    default: True\ntags:\n  layer: code\n  risk_category: supply_chain_attack\n  compliance:soc2: CC7.1\n  compliance:iso-27001: A.12.6.1\n",
                "parsed_content": {
                    "namespace": "jit.code",
                    "name": "Scan your code dependencies for vulnerabilities (SCA)",
                    "summary": "Integrate SCA tool into CI/CD so it automatically runs for every new PR.\n",
                    "description": "Code dependencies should be scanned for vulnerabilities, as vulnerable dependencies can cause a range of problems\nfor your project or the people who use it.\n",
                    "workflows": [
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-sca@latest",
                            "default": True
                        }
                    ],
                    "tags": {
                        "compliance:soc2": "CC7.1",
                        "compliance:iso-27001": "A.12.6.1",
                        "risk_category": "supply_chain_attack",
                        "layer": "code"
                    }
                },
                "plan_template_slugs": [
                    "plan-mvs-for-cloud-app",
                    "plan-iso-27001",
                    "plan-soc2",
                    "plan-owasp-serverless-top-10"
                ],
                "asset_types": [
                    "repo"
                ]
            },
            "workflow_templates": [
                {
                    "slug": "workflow-sca",
                    "name": "SCA Workflow",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  software-component-analysis:\n    asset_type: repo\n    default: True\n    if:\n      package_managers:\n      - pip\n      - composer\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run osv-scanner\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-osv-scanner-control\n          security_tool: https://github.com/google/osv-scanner\n        security_tool: osv-scanner\n      uses: ghcr.io/jitsecurity-controls/control-osv-scanner-alpine:latest\n      with:\n        args: --recursive \\${WORK_DIR:-.}\n    tags:\n      languages:\n      - python\n      - php_deps\n  software-component-analysis-go:\n    asset_type: repo\n    default: True\n    if:\n      package_managers:\n      - go_modules\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run nancy\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-nancy-control\n          security_tool: https://github.com/sonatype-nexus-community/nancy\n        security_tool: Nancy\n      uses: ghcr.io/jitsecurity-controls/control-nancy-alpine:latest\n    tags:\n      languages:\n      - go\n      - go_deps\n  software-component-analysis-js:\n    asset_type: repo\n    default: True\n    if:\n      package_managers:\n      - npm\n      - yarn\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run npm audit\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-dependency-check-node-control\n          security_tool: https://docs.npmjs.com/cli/v9/commands/npm-audit\n        security_tool: Npm-audit\n      uses: ghcr.io/jitsecurity-controls/control-npm-audit-slim:latest\n      with:\n        output_file: /code/jit-report/enriched-audit-results.json\n    tags:\n      languages:\n      - js_deps\nname: SCA Workflow\ntrigger:\n  True:\n  - item_activated\n  - resource_added\n  - pull_request_created\n  - pull_request_updated\n  - merge_default_branch\n  depends_on:\n  - workflow-enrichment-code\n  - manual_execution\n",
                    "depends_on": [
                        "workflow-enrichment-code"
                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "repo",
                        "repo",
                        "repo"
                    ],
                    "parsed_content": {
                        "name": "SCA Workflow",
                        "jobs": {
                            "software-component-analysis-js": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10,
                                    }
                                },
                                "if": {
                                    "package_managers": [
                                        "npm",
                                        "yarn"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run npm audit",
                                        "with": {
                                            "output_file": "/code/jit-report/enriched-audit-results.json"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-npm-audit-slim:latest",
                                        "tags": {
                                            "security_tool": "Npm-audit",
                                            "links": {
                                                "security_tool": "https://docs.npmjs.com/cli/v9/commands/npm-audit",
                                                "github": "https://github.com/jitsecurity-controls/jit-dependency-check-node-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "js_deps"
                                    ]
                                }
                            },
                            "software-component-analysis-go": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10,
                                    }
                                },
                                "if": {
                                    "package_managers": [
                                        "go_modules"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run nancy",
                                        "uses": "ghcr.io/jitsecurity-controls/control-nancy-alpine:latest",
                                        "tags": {
                                            "security_tool": "Nancy",
                                            "links": {
                                                "security_tool": "https://github.com/sonatype-nexus-community/nancy",
                                                "github": "https://github.com/jitsecurity-controls/jit-nancy-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "go",
                                        "go_deps"
                                    ]
                                }
                            },
                            "software-component-analysis": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10,
                                    }
                                },
                                "if": {
                                    "package_managers": [
                                        "pip",
                                        "composer"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run osv-scanner",
                                        "with": {
                                            "args": "--recursive \\${WORK_DIR:-.}"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-osv-scanner-alpine:latest",
                                        "tags": {
                                            "security_tool": "osv-scanner",
                                            "links": {
                                                "security_tool": "https://github.com/google/osv-scanner",
                                                "github": "https://github.com/jitsecurity-controls/jit-osv-scanner-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "python",
                                        "php_deps"
                                    ]
                                }
                            }
                        },
                        "trigger": {
                            "True": [
                                "item_activated",
                                "resource_added",
                                "pull_request_created",
                                "pull_request_updated",
                                "merge_default_branch"
                            ],
                            "depends_on": [
                                "workflow-enrichment-code"
                            ]
                        }
                    }
                }
            ]
        },
        "item-iac-kubernetes": {
            "item_template": {
                "slug": "item-iac-kubernetes",
                "name": "Scan Kubernetes configuration files",
                "type": "plan_item",
                "content": "namespace: jit.infrastructure\nname: Scan Kubernetes configuration files\ndescription: |\n  Scanning Kubernetes configuration files is important for ensuring the security and reliability of Kubernetes\n  deployments. With it you can maintain security best practices for Kubernetes and catch issues,\n  such as unsecured APIs, over-privileged containers, misconfigured resource limits and many more.\n  By identifying and mitigating these issues during development, you can reduce the likelihood of your workloads\n  being compromised and save time that would otherwise be spent resolving issues in a production environment.\nsummary: |\n  Jit integrates a Kubernetes IaC scanner into CI/CD to automatically scan the existing code base and every new PR.\nworkflows:\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-kubernetes-iac-misconfiguration-detection@latest\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-remediation-pr@latest\nrefs:\ntags:\n  layer: infrastructure\n  risk_category: supply_chain_attack\n",
                "parsed_content": {
                    "summary": "Jit integrates a Kubernetes IaC scanner into CI/CD to automatically scan the existing code base and every new PR.\n",
                    "refs": None,
                    "namespace": "jit.infrastructure",
                    "name": "Scan Kubernetes configuration files",
                    "description": "Scanning Kubernetes configuration files is important for ensuring the security and reliability of Kubernetes\ndeployments. With it you can maintain security best practices for Kubernetes and catch issues,\nsuch as unsecured APIs, over-privileged containers, misconfigured resource limits and many more.\nBy identifying and mitigating these issues during development, you can reduce the likelihood of your workloads\nbeing compromised and save time that would otherwise be spent resolving issues in a production environment.\n",
                    "workflows": [
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-kubernetes-iac-misconfiguration-detection@latest"
                        },
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-remediation-pr@latest"
                        }
                    ],
                    "tags": {
                        "layer": "infrastructure",
                        "risk_category": "supply_chain_attack"
                    }
                },
                "plan_template_slugs": [
                    "plan-mvs-for-cloud-app"
                ],
                "asset_types": [
                    "repo"
                ]
            },
            "workflow_templates": [
                {
                    "slug": "workflow-kubernetes-iac-misconfiguration-detection",
                    "name": "Kubernetes IaC Misconfiguration Detection Workflow",
                    "type": "workflow",
                    "default": None,
                    "content": "jobs:\n  iac-misconfig-detection-kubernetes:\n    asset_type: repo\n    default: True\n    if:\n      frameworks:\n      - kubernetes\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run kubescape\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-kubescape-control\n          security_tool: https://github.com/kubescape/kubescape\n        security_tool: kubescape\n      uses: ghcr.io/jitsecurity-controls/control-kubescape-slim:main\n      with:\n        args: scan -v --format json --format-version v2 --output raw-kubescape-results.json\n          .\n        output_file: /code/results.json\n    tags:\n      languages:\n      - Manifest files\n      - Helm Charts\nname: Kubernetes IaC Misconfiguration Detection Workflow\ntrigger:\n  True:\n  - item_activated\n  - resource_added\n  - pull_request_created\n  - pull_request_updated\n  - merge_default_branch\n  depends_on:\n  - workflow-enrichment-code\n  - manual_execution\n",
                    "depends_on": [
                        "workflow-enrichment-code"
                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "repo"
                    ],
                    "parsed_content": {
                        "name": "Kubernetes IaC Misconfiguration Detection Workflow",
                        "jobs": {
                            "iac-misconfig-detection-kubernetes": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10,
                                    }
                                },
                                "if": {
                                    "frameworks": [
                                        "kubernetes"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run kubescape",
                                        "with": {
                                            "args": "scan -v --format json --format-version v2 --output raw-kubescape-results.json .",
                                            "output_file": "/code/results.json"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-kubescape-slim:main",
                                        "tags": {
                                            "security_tool": "kubescape",
                                            "links": {
                                                "security_tool": "https://github.com/kubescape/kubescape",
                                                "github": "https://github.com/jitsecurity-controls/jit-kubescape-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "Manifest files",
                                        "Helm Charts"
                                    ]
                                }
                            }
                        },
                        "trigger": {
                            "True": [
                                "item_activated",
                                "resource_added",
                                "pull_request_created",
                                "pull_request_updated",
                                "merge_default_branch"
                            ],
                            "depends_on": [
                                "workflow-enrichment-code"
                            ]
                        }
                    }
                },
                {
                    "slug": "workflow-remediation-pr",
                    "name": "Remediation Pull Request Workflow",
                    "type": "workflow",
                    "default": None,
                    "content": "jobs:\n  remediation-pr:\n    asset_type: repo\n    default: True\n    runner:\n      setup:\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run Jit Remediation\n      tags:\n        is_hidden: True\n        links: []\n        security_tool: Jit-remediation\n        workflow_type: remediation\n      uses: ghcr.io/jitsecurity-controls/open-remediation-pr-alpine:latest\n      with:\n        args: --github-token ${{fromJSON(github.event.inputs.client_payload).payload.github_token}}\n          --fix-pr-config ${{fromJSON(github.event.inputs.client_payload).payload.fix_pr_config}}\n          --output-file \\$REPORT_FILE\n        output_file: /opt/code/jit-report/results.json\nname: Remediation Pull Request Workflow\ntrigger:\n  True:\n  - open_fix_pull_request\n",
                    "depends_on": [

                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "repo"
                    ],
                    "parsed_content": {
                        "name": "Remediation Pull Request Workflow",
                        "jobs": {
                            "remediation-pr": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "timeout_minutes": 10
                                    }
                                },
                                "steps": [
                                    {
                                        "name": "Run Jit Remediation",
                                        "with": {
                                            "args": "--github-token ${{fromJSON(github.event.inputs.client_payload).payload.github_token}} --fix-pr-config ${{fromJSON(github.event.inputs.client_payload).payload.fix_pr_config}} --output-file \\$REPORT_FILE",
                                            "output_file": "/opt/code/jit-report/results.json"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/open-remediation-pr-alpine:latest",
                                        "tags": {
                                            "is_hidden": True,
                                            "security_tool": "Jit-remediation",
                                            "links": [

                                            ],
                                            "workflow_type": "remediation"
                                        }
                                    }
                                ]
                            }
                        },
                        "trigger": {
                            "True": [
                                "open_fix_pull_request"
                            ]
                        }
                    }
                }
            ]
        },
        "item-iac-misconfiguration-detection": {
            "item_template": {
                "slug": "item-iac-misconfiguration-detection",
                "name": "Scan your infrastructure-as-code (IaC) for misconfigurations",
                "type": "plan_item",
                "content": "namespace: jit.infrastructure\nname: Scan your infrastructure-as-code (IaC) for misconfigurations\ndescription: |\n  Cloud misconfigurations occur when resources have not been constructed properly, leaving your systems vulnerable\n  to attack. Cloud environment misconfigurations can cause system outages, unwanted downtime, or security risks.\n  Causes can include overly complex environments, insufficient security practice knowledge, and human error due to\n  manual processes.\nsummary: |\n  Jit integrates SAST for IaC into CI/CD so it automatically runs for every new PR.\nworkflows:\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-iac-misconfiguration-detection@latest\n    default: True\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-remediation-pr@latest\n    default: True\ntags:\n  layer: infrastructure\n  risk_category: supply_chain_attack\n  compliance:soc2: CC7.1\n  compliance:iso-27001: A.12.6.1\n",
                "parsed_content": {
                    "namespace": "jit.infrastructure",
                    "name": "Scan your infrastructure-as-code (IaC) for misconfigurations",
                    "summary": "Jit integrates SAST for IaC into CI/CD so it automatically runs for every new PR.\n",
                    "description": "Cloud misconfigurations occur when resources have not been constructed properly, leaving your systems vulnerable\nto attack. Cloud environment misconfigurations can cause system outages, unwanted downtime, or security risks.\nCauses can include overly complex environments, insufficient security practice knowledge, and human error due to\nmanual processes.\n",
                    "workflows": [
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-iac-misconfiguration-detection@latest",
                            "default": True
                        },
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-remediation-pr@latest",
                            "default": True
                        }
                    ],
                    "tags": {
                        "compliance:soc2": "CC7.1",
                        "compliance:iso-27001": "A.12.6.1",
                        "risk_category": "supply_chain_attack",
                        "layer": "infrastructure"
                    }
                },
                "plan_template_slugs": [
                    "plan-iso-27001",
                    "plan-soc2",
                    "plan-mvs-for-cloud-app"
                ],
                "asset_types": [
                    "repo"
                ]
            },
            "workflow_templates": [
                {
                    "slug": "workflow-iac-misconfiguration-detection",
                    "name": "IaC Misconfiguration Detection Workflow",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  iac-misconfig-detection-cloudformation:\n    asset_type: repo\n    default: True\n    if:\n      frameworks:\n      - cloudformation\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run KICS (cloudformation)\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-cloud-infrastructure-misconfiguration-control\n          security_tool: https://github.com/Checkmarx/kics\n        security_tool: Kics\n      uses: ghcr.io/jitsecurity-controls/control-kics-alpine:latest\n      with:\n        args: scan -t CloudFormation -p \\${WORK_DIR:-.} -o \\$REPORT_FILE -f json --config\n          \\/cloudformation-config.yaml --disable-secrets\n        output_file: /code/jit-report/results.json\n    tags:\n      languages:\n      - cloudformation\n      - aws_cdk_output\n  iac-misconfig-detection-pulumi:\n    asset_type: repo\n    default: True\n    if:\n      frameworks:\n      - pulumi\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run KICS (pulumi)\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-cloud-infrastructure-misconfiguration-control\n          security_tool: https://github.com/Checkmarx/kics\n        security_tool: Kics\n      uses: ghcr.io/jitsecurity-controls/control-kics-alpine:latest\n      with:\n        args: scan -t Pulumi -p \\${WORK_DIR:-.} -o \\$REPORT_FILE -f json --config\n          \\/pulumi-config.yaml --disable-secrets\n        output_file: /code/jit-report/results.json\n    tags:\n      languages:\n      - pulumi\n  iac-misconfig-detection-terraform:\n    asset_type: repo\n    default: True\n    if:\n      frameworks:\n      - terraform\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run KICS (terraform)\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-cloud-infrastructure-misconfiguration-control\n          security_tool: https://github.com/Checkmarx/kics\n        security_tool: Kics\n      uses: ghcr.io/jitsecurity-controls/control-kics-alpine:latest\n      with:\n        args: scan -t Terraform -p \\${WORK_DIR:-.} -o \\$REPORT_FILE -f json --config\n          \\/terraform-config.yaml --disable-secrets\n        output_file: /code/jit-report/results.json\n    tags:\n      languages:\n      - terraform\nname: IaC Misconfiguration Detection Workflow\ntrigger:\n  True:\n  - item_activated\n  - resource_added\n  - pull_request_created\n  - pull_request_updated\n  - merge_default_branch\n  depends_on:\n  - workflow-enrichment-code\n  - manual_execution\n",
                    "depends_on": [
                        "workflow-enrichment-code"
                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "repo",
                        "repo",
                        "repo",
                        "repo"
                    ],
                    "parsed_content": {
                        "name": "IaC Misconfiguration Detection Workflow",
                        "jobs": {
                            "iac-misconfig-detection-pulumi": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10,
                                    }
                                },
                                "if": {
                                    "frameworks": [
                                        "pulumi"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run KICS (pulumi)",
                                        "with": {
                                            "args": "scan -t Pulumi -p \\${WORK_DIR:-.} -o \\$REPORT_FILE -f json --config \\/pulumi-config.yaml --disable-secrets",
                                            "output_file": "/code/jit-report/results.json"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-kics-alpine:latest",
                                        "tags": {
                                            "security_tool": "Kics",
                                            "links": {
                                                "security_tool": "https://github.com/Checkmarx/kics",
                                                "github": "https://github.com/jitsecurity-controls/jit-cloud-infrastructure-misconfiguration-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "pulumi"
                                    ]
                                }
                            },
                            "iac-misconfig-detection-cloudformation": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10,
                                    }
                                },
                                "if": {
                                    "frameworks": [
                                        "cloudformation"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run KICS (cloudformation)",
                                        "with": {
                                            "args": "scan -t CloudFormation -p \\${WORK_DIR:-.} -o \\$REPORT_FILE -f json --config \\/cloudformation-config.yaml --disable-secrets",
                                            "output_file": "/code/jit-report/results.json"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-kics-alpine:latest",
                                        "tags": {
                                            "security_tool": "Kics",
                                            "links": {
                                                "security_tool": "https://github.com/Checkmarx/kics",
                                                "github": "https://github.com/jitsecurity-controls/jit-cloud-infrastructure-misconfiguration-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "cloudformation",
                                        "aws_cdk_output"
                                    ]
                                }
                            },
                            "iac-misconfig-detection-terraform": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10,
                                    }
                                },
                                "if": {
                                    "frameworks": [
                                        "terraform"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run KICS (terraform)",
                                        "with": {
                                            "args": "scan -t Terraform -p \\${WORK_DIR:-.} -o \\$REPORT_FILE -f json --config \\/terraform-config.yaml --disable-secrets",
                                            "output_file": "/code/jit-report/results.json"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-kics-alpine:latest",
                                        "tags": {
                                            "security_tool": "Kics",
                                            "links": {
                                                "security_tool": "https://github.com/Checkmarx/kics",
                                                "github": "https://github.com/jitsecurity-controls/jit-cloud-infrastructure-misconfiguration-control"
                                            }
                                        }
                                    }
                                ],
                                "tags": {
                                    "languages": [
                                        "terraform"
                                    ]
                                }
                            }
                        },
                        "trigger": {
                            "True": [
                                "item_activated",
                                "resource_added",
                                "pull_request_created",
                                "pull_request_updated",
                                "merge_default_branch"
                            ],
                            "depends_on": [
                                "workflow-enrichment-code"
                            ]
                        }
                    }
                },
                {
                    "slug": "workflow-remediation-pr",
                    "name": "Remediation Pull Request Workflow",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  remediation-pr:\n    asset_type: repo\n    default: True\n    runner:\n      setup:\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run Jit Remediation\n      tags:\n        is_hidden: True\n        links: []\n        security_tool: Jit-remediation\n        workflow_type: remediation\n      uses: ghcr.io/jitsecurity-controls/open-remediation-pr-alpine:latest\n      with:\n        args: --github-token ${{fromJSON(github.event.inputs.client_payload).payload.github_token}}\n          --fix-pr-config ${{fromJSON(github.event.inputs.client_payload).payload.fix_pr_config}}\n          --output-file \\$REPORT_FILE\n        output_file: /opt/code/jit-report/results.json\nname: Remediation Pull Request Workflow\ntrigger:\n  True:\n  - open_fix_pull_request\n",
                    "depends_on": [

                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "repo"
                    ],
                    "parsed_content": {
                        "name": "Remediation Pull Request Workflow",
                        "jobs": {
                            "remediation-pr": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "timeout_minutes": 10
                                    }
                                },
                                "steps": [
                                    {
                                        "name": "Run Jit Remediation",
                                        "with": {
                                            "args": "--github-token ${{fromJSON(github.event.inputs.client_payload).payload.github_token}} --fix-pr-config ${{fromJSON(github.event.inputs.client_payload).payload.fix_pr_config}} --output-file \\$REPORT_FILE",
                                            "output_file": "/opt/code/jit-report/results.json"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/open-remediation-pr-alpine:latest",
                                        "tags": {
                                            "is_hidden": True,
                                            "security_tool": "Jit-remediation",
                                            "links": [

                                            ],
                                            "workflow_type": "remediation"
                                        }
                                    }
                                ]
                            }
                        },
                        "trigger": {
                            "True": [
                                "open_fix_pull_request"
                            ]
                        }
                    }
                }
            ]
        },
        "item-mfa-cloud-providers": {
            "item_template": {
                "slug": "item-mfa-cloud-providers",
                "name": "Verify that the users of your AWS accounts have enabled MFA",
                "type": "plan_item",
                "content": "namespace: jit.third_party_app\nname: Verify that the users of your AWS accounts have enabled MFA\ndescription: |\n  Your employees should all use multi-factor authentication. By adding MFA, you add an extra layer of security. Should\n  your employee’s password get stolen, the attacker would still be locked out unless they have access to the second\n  factor (e.g. phone app or text) as well.\nsummary: |\n  Ensure you have MFA enabled for all your users.\nworkflows:\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-mfa-aws-checker@latest\n    default: True\ntags:\n  layer: infrastructure\n  risk_category: access_control\n",
                "parsed_content": {
                    "namespace": "jit.third_party_app",
                    "name": "Verify that the users of your AWS accounts have enabled MFA",
                    "summary": "Ensure you have MFA enabled for all your users.\n",
                    "description": "Your employees should all use multi-factor authentication. By adding MFA, you add an extra layer of security. Should\nyour employee’s password get stolen, the attacker would still be locked out unless they have access to the second\nfactor (e.g. phone app or text) as well.\n",
                    "workflows": [
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-mfa-aws-checker@latest",
                            "default": True
                        }
                    ],
                    "tags": {
                        "layer": "infrastructure",
                        "risk_category": "access_control"
                    }
                },
                "plan_template_slugs": [
                    "plan-mvs-for-cloud-app"
                ],
                "asset_types": [
                    "aws_account"
                ]
            },
            "workflow_templates": [
                {
                    "slug": "workflow-mfa-aws-checker",
                    "name": "MFA Checker on AWS Workflow",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  mfa-aws-checker:\n    asset_type: aws_account\n    default: True\n    runner:\n      setup:\n        auth_type: aws_iam_role\n      type: jit\n    steps:\n    - name: Run MFA checker\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-aws-mfa-control\n        security_tool: AWS MFA Checker\n      uses: 899025839375.dkr.ecr.us-east-1.amazonaws.com/aws-mfa:latest\n      with:\n        env:\n          AWS_ACCESS_KEY_ID: ${{ context.auth.config.aws_access_key_id }}\n          AWS_REGION_NAME: ${{ context.auth.config.region_name }}\n          AWS_SECRET_ACCESS_KEY: ${{ context.auth.config.aws_secret_access_key }}\n          AWS_SESSION_TOKEN: ${{ context.auth.config.aws_session_token }}\nname: MFA Checker on AWS Workflow\ntrigger:\n  True:\n  - item_activated\n  - resource_added\n  - schedule(\"daily\")\n  - manual_execution\n",
                    "depends_on": [

                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "aws_account"
                    ],
                    "parsed_content": {
                        "name": "MFA Checker on AWS Workflow",
                        "jobs": {
                            "mfa-aws-checker": {
                                "asset_type": "aws_account",
                                "default": True,
                                "runner": {
                                    "type": "jit",
                                    "setup": {
                                        "auth_type": "aws_iam_role"
                                    }
                                },
                                "steps": [
                                    {
                                        "name": "Run MFA checker",
                                        "with": {
                                            "env": {
                                                "AWS_SESSION_TOKEN": "${{ context.auth.config.aws_session_token }}",
                                                "AWS_REGION_NAME": "${{ context.auth.config.region_name }}",
                                                "AWS_ACCESS_KEY_ID": "${{ context.auth.config.aws_access_key_id }}",
                                                "AWS_SECRET_ACCESS_KEY": "${{ context.auth.config.aws_secret_access_key }}"
                                            }
                                        },
                                        "uses": "899025839375.dkr.ecr.us-east-1.amazonaws.com/aws-mfa:latest",
                                        "tags": {
                                            "security_tool": "AWS MFA Checker",
                                            "links": {
                                                "github": "https://github.com/jitsecurity-controls/jit-aws-mfa-control"
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                        "trigger": {
                            "True": [
                                "item_activated",
                                "resource_added",
                                "schedule(\"daily\")"
                            ]
                        }
                    }
                }
            ]
        },
        "item-mfa-scm": {
            "item_template": {
                "slug": "item-mfa-scm",
                "name": "Verify that MFA for your GitHub organization is enabled",
                "type": "plan_item",
                "content": "namespace: jit.third_party_app\nname: Verify that MFA for your GitHub organization is enabled\ndescription: |\n  Your employees should all use multi factor authentication. By adding MFA, you add an extra layer of security. Should\n  your employee’s password get stolen, the attacker would still be locked out unless they have access to the second\n  factor (e.g. phone app or text) as well.\nsummary: |\n  Ensure you have MFA enabled for all your users.\nworkflows:\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-mfa-github-checker@latest\n    default: True\ntags:\n  layer: third_party_app\n  risk_category: access_control\n",
                "parsed_content": {
                    "namespace": "jit.third_party_app",
                    "name": "Verify that MFA for your GitHub organization is enabled",
                    "summary": "Ensure you have MFA enabled for all your users.\n",
                    "description": "Your employees should all use multi factor authentication. By adding MFA, you add an extra layer of security. Should\nyour employee’s password get stolen, the attacker would still be locked out unless they have access to the second\nfactor (e.g. phone app or text) as well.\n",
                    "workflows": [
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-mfa-github-checker@latest",
                            "default": True
                        }
                    ],
                    "tags": {
                        "layer": "third_party_app",
                        "risk_category": "access_control"
                    }
                },
                "plan_template_slugs": [
                    "plan-mvs-for-cloud-app"
                ],
                "asset_types": [
                    "org"
                ]
            },
            "workflow_templates": [
                {
                    "slug": "workflow-mfa-github-checker",
                    "name": "MFA Checker on Github Workflow",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  mfa-github-checker:\n    asset_type: org\n    default: True\n    runner:\n      setup:\n        auth_type: scm_token\n      type: jit\n    steps:\n    - name: Run MFA checker\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-github-mfa-control\n        security_tool: Github MFA Checker\n      uses: 899025839375.dkr.ecr.us-east-1.amazonaws.com/github-mfa:latest\n      with:\n        args: --organization-name ${{ context.asset.asset_name }}\n        env:\n          GITHUB_TOKEN: ${{ context.auth.config.github_token }}\nname: MFA Checker on Github Workflow\ntrigger:\n  True:\n  - item_activated\n  - resource_added\n  - schedule(\"daily\")\n  - manual_execution\n",
                    "depends_on": [

                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "org"
                    ],
                    "parsed_content": {
                        "name": "MFA Checker on Github Workflow",
                        "jobs": {
                            "mfa-github-checker": {
                                "asset_type": "org",
                                "default": True,
                                "runner": {
                                    "type": "jit",
                                    "setup": {
                                        "auth_type": "scm_token"
                                    }
                                },
                                "steps": [
                                    {
                                        "name": "Run MFA checker",
                                        "with": {
                                            "args": "--organization-name ${{ context.asset.asset_name }}",
                                            "env": {
                                                "GITHUB_TOKEN": "${{ context.auth.config.scm_token }}"
                                            }
                                        },
                                        "uses": "899025839375.dkr.ecr.us-east-1.amazonaws.com/github-mfa:latest",
                                        "tags": {
                                            "security_tool": "Github MFA Checker",
                                            "links": {
                                                "github": "https://github.com/jitsecurity-controls/jit-github-mfa-control"
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                        "trigger": {
                            "True": [
                                "item_activated",
                                "resource_added",
                                "schedule(\"daily\")"
                            ]
                        }
                    }
                }
            ]
        },
        "item-runtime-misconfiguration-detection": {
            "item_template": {
                "slug": "item-runtime-misconfiguration-detection",
                "name": "Scan infrastructure for runtime misconfigurations",
                "type": "plan_item",
                "content": "namespace: jit.infrastructure\nname: Scan infrastructure for runtime misconfigurations\ndescription: |\n  Cloud misconfigurations occur when resources have not been constructed properly, leaving your systems vulnerable\n  to attack. Cloud environment misconfigurations can cause system outages, unwanted downtime, or security risks.\n  Causes may include overly complex environments, insufficient security practice knowledge, and human error due to\n  manual processes.\nsummary: |\n  Run AWS misconfiguration scanner on schedule.\nworkflows:\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-runtime-misconfiguration-detection@latest\n    default: True\ntags:\n  layer: infrastructure\n  risk_category: supply_chain_attack\n",
                "parsed_content": {
                    "namespace": "jit.infrastructure",
                    "name": "Scan infrastructure for runtime misconfigurations",
                    "summary": "Run AWS misconfiguration scanner on schedule.\n",
                    "description": "Cloud misconfigurations occur when resources have not been constructed properly, leaving your systems vulnerable\nto attack. Cloud environment misconfigurations can cause system outages, unwanted downtime, or security risks.\nCauses may include overly complex environments, insufficient security practice knowledge, and human error due to\nmanual processes.\n",
                    "workflows": [
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-runtime-misconfiguration-detection@latest",
                            "default": True
                        }
                    ],
                    "tags": {
                        "layer": "infrastructure",
                        "risk_category": "supply_chain_attack"
                    }
                },
                "plan_template_slugs": [
                    "plan-mvs-for-cloud-app",
                    "plan-iso-27001",
                    "plan-soc2",
                    "plan-owasp-serverless-top-10"
                ],
                "asset_types": [
                    "aws_account"
                ]
            },
            "workflow_templates": [
                {
                    "slug": "workflow-runtime-misconfiguration-detection",
                    "name": "Infrastructure Runtime Misconfiguration Detection Workflow (AWS)",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  runtime-misconfig-detection-aws:\n    asset_type: aws_account\n    default: True\n    runner:\n      setup:\n        auth_type: aws_iam_role\n        timeout_minutes: 10\n      type: jit\n    steps:\n    - name: Run Prowler For AWS\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-prowler-control\n          security_tool: https://github.com/prowler-cloud/prowler\n        security_tool: Prowler\n      uses: 899025839375.dkr.ecr.us-east-1.amazonaws.com/prowler:latest\n      with:\n        env:\n          AWS_ACCESS_KEY_ID: ${{ context.auth.config.aws_access_key_id }}\n          AWS_SECRET_ACCESS_KEY: ${{ context.auth.config.aws_secret_access_key }}\n          AWS_SESSION_TOKEN: ${{ context.auth.config.aws_session_token }}\n          JIT_CONFIG_CONTENT: ${{ context.config }}\nname: Infrastructure Runtime Misconfiguration Detection Workflow (AWS)\ntrigger:\n  True:\n  - item_activated\n  - resource_added\n  - schedule(\"daily\")\n  - manual_execution\n",
                    "depends_on": [

                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "aws_account"
                    ],
                    "parsed_content": {
                        "name": "Infrastructure Runtime Misconfiguration Detection Workflow (AWS)",
                        "jobs": {
                            "runtime-misconfig-detection-aws": {
                                "asset_type": "aws_account",
                                "default": True,
                                "runner": {
                                    "type": "jit",
                                    "setup": {
                                        "auth_type": "aws_iam_role",
                                        "timeout_minutes": 10,
                                    }
                                },
                                "steps": [
                                    {
                                        "name": "Run Prowler For AWS",
                                        "with": {
                                            "env": {
                                                "AWS_SESSION_TOKEN": "${{ context.auth.config.aws_session_token }}",
                                                "JIT_CONFIG_CONTENT": "${{ context.config }}",
                                                "AWS_ACCESS_KEY_ID": "${{ context.auth.config.aws_access_key_id }}",
                                                "AWS_SECRET_ACCESS_KEY": "${{ context.auth.config.aws_secret_access_key }}"
                                            }
                                        },
                                        "uses": "899025839375.dkr.ecr.us-east-1.amazonaws.com/prowler:latest",
                                        "tags": {
                                            "security_tool": "Prowler",
                                            "links": {
                                                "security_tool": "https://github.com/prowler-cloud/prowler",
                                                "github": "https://github.com/jitsecurity-controls/jit-prowler-control"
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                        "trigger": {
                            "True": [
                                "item_activated",
                                "resource_added",
                                "schedule(\"daily\")",
                                "manual_execution",
                            ]
                        }
                    }
                },
                {
                    "slug": "workflow-runtime-misconfiguration-detection-deployment",
                    "name": "Infrastructure Runtime Misconfiguration Detection Workflow (AWS)",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  runtime-misconfig-detection-aws:\n    asset_type: aws_account\n    default: True\n    runner:\n      setup:\n        auth_type: aws_iam_role\n        timeout_minutes: 10\n      type: jit\n    steps:\n    - name: Run Prowler For AWS\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-prowler-control\n          security_tool: https://github.com/prowler-cloud/prowler\n        security_tool: Prowler\n      uses: 899025839375.dkr.ecr.us-east-1.amazonaws.com/prowler:latest\n      with:\n        env:\n          AWS_ACCESS_KEY_ID: ${{ context.auth.config.aws_access_key_id }}\n          AWS_SECRET_ACCESS_KEY: ${{ context.auth.config.aws_secret_access_key }}\n          AWS_SESSION_TOKEN: ${{ context.auth.config.aws_session_token }}\n          JIT_CONFIG_CONTENT: ${{ context.config }}\nname: Infrastructure Runtime Misconfiguration Detection Workflow (AWS)\ntrigger:\n  True:\n  - deployment\n",
                    "depends_on": [

                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "aws_account"
                    ],
                    "parsed_content": {
                        "name": "Infrastructure Runtime Misconfiguration Detection Workflow (AWS)",
                        "jobs": {
                            "runtime-misconfig-detection-aws": {
                                "asset_type": "aws_account",
                                "default": True,
                                "runner": {
                                    "type": "jit",
                                    "setup": {
                                        "auth_type": "aws_iam_role",
                                        "timeout_minutes": 10,
                                    }
                                },
                                "steps": [
                                    {
                                        "name": "Run Prowler For AWS",
                                        "with": {
                                            "env": {
                                                "AWS_SESSION_TOKEN": "${{ context.auth.config.aws_session_token }}",
                                                "JIT_CONFIG_CONTENT": "${{ context.config }}",
                                                "AWS_ACCESS_KEY_ID": "${{ context.auth.config.aws_access_key_id }}",
                                                "AWS_SECRET_ACCESS_KEY": "${{ context.auth.config.aws_secret_access_key }}"
                                            }
                                        },
                                        "uses": "899025839375.dkr.ecr.us-east-1.amazonaws.com/prowler:latest",
                                        "tags": {
                                            "security_tool": "Prowler",
                                            "links": {
                                                "security_tool": "https://github.com/prowler-cloud/prowler",
                                                "github": "https://github.com/jitsecurity-controls/jit-prowler-control"
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                        "trigger": {
                            "True": [
                                "deployment"
                            ]
                        }
                    }
                }
            ]
        },
        "item-secret-detection": {
            "item_template": {
                "slug": "item-secret-detection",
                "name": "Scan code for hard-coded secrets",
                "type": "plan_item",
                "content": "namespace: jit.code\nname: Scan code for hard-coded secrets\ndescription: |\n  Hard-coded secrets can be exploited by attackers to gain unauthorized access to the password-protected asset.\nsummary: |\n  Integrate secret scanner into CI/CD so automatically runs for every new PR.\nworkflows:\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-secret-detection@latest\n    default: True\ntags:\n  layer: code\n  risk_category: secret_leaks\n  compliance:soc2: CC7.1\n  compliance:iso-27001: A.12.6.1\n",
                "parsed_content": {
                    "namespace": "jit.code",
                    "name": "Scan code for hard-coded secrets",
                    "summary": "Integrate secret scanner into CI/CD so automatically runs for every new PR.\n",
                    "description": "Hard-coded secrets can be exploited by attackers to gain unauthorized access to the password-protected asset.\n",
                    "workflows": [
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-secret-detection@latest",
                            "default": True
                        }
                    ],
                    "tags": {
                        "compliance:soc2": "CC7.1",
                        "compliance:iso-27001": "A.12.6.1",
                        "risk_category": "secret_leaks",
                        "layer": "code"
                    }
                },
                "plan_template_slugs": [
                    "plan-iso-27001",
                    "plan-soc2",
                    "plan-mvs-for-cloud-app"
                ],
                "asset_types": [
                    "repo"
                ]
            },
            "workflow_templates": [
                {
                    "slug": "workflow-secret-detection",
                    "name": "Secret Detection Workflow",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  secret-detection:\n    asset_type: repo\n    default: True\n    if:\n      mime_types:\n      - text\n    runner:\n      setup:\n        checkout: True\n        timeout_minutes: 10\n      type: github_actions\n    steps:\n    - name: Run Gitleaks\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-secrets-detection-control\n          security_tool: https://github.com/zricethezav/gitleaks\n        security_tool: Gitleaks\n      uses: ghcr.io/jitsecurity-controls/control-gitleaks-alpine:latest\n      with:\n        args: detect --config \\$GITLEAKS_CONFIG_FILE_PATH --source \\${WORK_DIR:-.}\n          -v --report-format json --report-path \\$REPORT_FILE --redact --no-git --exit-code\n          0\n        output_file: /tmp/report.json\nname: Secret Detection Workflow\ntrigger:\n  True:\n  - item_activated\n  - resource_added\n  - pull_request_created\n  - pull_request_updated\n  - merge_default_branch\n  depends_on:\n  - workflow-enrichment-code\n  - manual_execution\n",
                    "depends_on": [
                        "workflow-enrichment-code"
                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "repo"
                    ],
                    "parsed_content": {
                        "name": "Secret Detection Workflow",
                        "jobs": {
                            "secret-detection": {
                                "asset_type": "repo",
                                "default": True,
                                "runner": {
                                    "type": "github_actions",
                                    "setup": {
                                        "checkout": True,
                                        "timeout_minutes": 10,
                                    }
                                },
                                "if": {
                                    "mime_types": [
                                        "text"
                                    ]
                                },
                                "steps": [
                                    {
                                        "name": "Run Gitleaks",
                                        "with": {
                                            "args": "detect --config \\$GITLEAKS_CONFIG_FILE_PATH --source \\${WORK_DIR:-.} -v --report-format json --report-path \\$REPORT_FILE --redact --no-git --exit-code 0",
                                            "output_file": "/tmp/report.json"
                                        },
                                        "uses": "ghcr.io/jitsecurity-controls/control-gitleaks-alpine:latest",
                                        "tags": {
                                            "security_tool": "Gitleaks",
                                            "links": {
                                                "security_tool": "https://github.com/zricethezav/gitleaks",
                                                "github": "https://github.com/jitsecurity-controls/jit-secrets-detection-control"
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                        "trigger": {
                            "True": [
                                "item_activated",
                                "resource_added",
                                "pull_request_created",
                                "pull_request_updated",
                                "merge_default_branch"
                            ],
                            "depends_on": [
                                "workflow-enrichment-code"
                            ]
                        }
                    }
                }
            ]
        },
        "item-web-app-scanner": {
            "item_template": {
                "slug": "item-web-app-scanner",
                "name": "Scan your web application for vulnerabilities",
                "type": "plan_item",
                "content": "namespace: jit.runtime\nname: Scan your web application for vulnerabilities\ndescription: |\n  Web application scanners, also referred to as web application vulnerability scanners, are automated tools that scan web\n  applications to look for security vulnerabilities. This is an efficient way to check your web application against a\n  list of known vulnerabilities and identify security weaknesses. This scanner runs an unauthenticated or authenticated\n  web application scanning. The functionality available to authenticated users is often more sensitive than\n  unauthenticated users which means a vulnerability identified in an authenticated part of an application is likely\n  to have a greater impact than an unauthenticated users.\nsummary: Run a web application scanner on schedule.\nworkflows:\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-web-app-scanner@latest\n    default: True\n  - uses: jitsecurity-controls/jit-plans/workflows/workflow-web-app-scanner-deployment@latest\n    default: True\ntags:\n  layer: runtime\n  risk_category: runtime_vulnerability\n",
                "parsed_content": {
                    "namespace": "jit.runtime",
                    "name": "Scan your web application for vulnerabilities",
                    "summary": "Run a web application scanner on schedule.",
                    "description": "Web application scanners, also referred to as web application vulnerability scanners, are automated tools that scan web\napplications to look for security vulnerabilities. This is an efficient way to check your web application against a\nlist of known vulnerabilities and identify security weaknesses. This scanner runs an unauthenticated or authenticated\nweb application scanning. The functionality available to authenticated users is often more sensitive than\nunauthenticated users which means a vulnerability identified in an authenticated part of an application is likely\nto have a greater impact than an unauthenticated users.\n",
                    "workflows": [
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-web-app-scanner@latest",
                            "default": True
                        },
                        {
                            "uses": "jitsecurity-controls/jit-plans/workflows/workflow-web-app-scanner-deployment@latest",
                            "default": True
                        }
                    ],
                    "tags": {
                        "layer": "runtime",
                        "risk_category": "runtime_vulnerability"
                    }
                },
                "plan_template_slugs": [
                    "plan-mvs-for-cloud-app",
                    "plan-owasp-serverless-top-10"
                ],
                "asset_types": [
                    "web"
                ]
            },
            "workflow_templates": [
                {
                    "slug": "workflow-web-app-scanner",
                    "name": "Web App Security Workflow",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  web-security-detection:\n    asset_type: web\n    default: True\n    runner:\n      setup:\n        timeout_minutes: 10\n      type: jit\n    steps:\n    - name: Run ZAP\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-zap-fullscan-control\n          security_tool: https://www.zaproxy.org/docs/docker/full-scan/\n        security_tool: Zap\n      uses: 899025839375.dkr.ecr.us-east-1.amazonaws.com/zap:latest\n      with:\n        args: \\'--scan_mode web --authentication_mode ${{ context.asset.authentication_mode\n          }} --target_url ${{ context.asset.target_url }} --exclude_paths ${{ context.asset.exclude_paths\n          }} --api_domain ${{ context.asset.api_domain }} --login_url ${{ context.asset.login_page_url\n          }} --username ${{ context.asset.username }} --username_selector ${{ context.asset.username_css_selector\n          }} --password_selector ${{ context.asset.password_css_selector }} --rule_set_path\n          rule_sets/comprehensive-web.yml\n\n          \\'\n        env:\n          AUTHENTICATION_VALUE: ${{ jit_secrets.web_scan_authentication_value }}\n          JIT_CONFIG_CONTENT: ${{ context.config }}\n          PASSWORD: ${{ jit_secrets.web_scan_password }}\nname: Web App Security Workflow\ntrigger:\n  True:\n  - item_activated\n  - resource_added\n  - schedule(\"daily\")\n  - manual_execution\n",
                    "depends_on": [

                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "web"
                    ],
                    "parsed_content": {
                        "name": "Web App Security Workflow",
                        "jobs": {
                            "web-security-detection": {
                                "asset_type": "web",
                                "default": True,
                                "runner": {
                                    "type": "jit",
                                    "setup": {
                                        "timeout_minutes": 10,
                                    }
                                },
                                "steps": [
                                    {
                                        "name": "Run ZAP",
                                        "with": {
                                            "args": "--scan_mode web --authentication_mode ${{ context.asset.authentication_mode }} --target_url ${{ context.asset.target_url }} --exclude_paths ${{ context.asset.exclude_paths }} --api_domain ${{ context.asset.api_domain }} --login_url ${{ context.asset.login_page_url }} --username ${{ context.asset.username }} --username_selector ${{ context.asset.username_css_selector }} --password_selector ${{ context.asset.password_css_selector }} --rule_set_path rule_sets/comprehensive-web.yml\n",
                                            "env": {
                                                "PASSWORD": "${{ jit_secrets.web_scan_password }}",
                                                "AUTHENTICATION_VALUE": "${{ jit_secrets.web_scan_authentication_value }}",
                                                "JIT_CONFIG_CONTENT": "${{ context.config }}"
                                            }
                                        },
                                        "uses": "899025839375.dkr.ecr.us-east-1.amazonaws.com/zap:latest",
                                        "tags": {
                                            "security_tool": "Zap",
                                            "links": {
                                                "security_tool": "https://www.zaproxy.org/docs/docker/full-scan/",
                                                "github": "https://github.com/jitsecurity-controls/jit-zap-fullscan-control"
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                        "trigger": {
                            "True": [
                                "item_activated",
                                "resource_added",
                                "schedule(\"daily\")"
                            ]
                        }
                    }
                },
                {
                    "slug": "workflow-web-app-scanner-deployment",
                    "name": "Web App Security Deployment Workflow",
                    "type": "workflow",
                    "default": True,
                    "content": "jobs:\n  web-security-detection:\n    asset_type: web\n    default: True\n    runner:\n      setup:\n        timeout_minutes: 10\n      type: jit\n    steps:\n    - name: Run ZAP\n      tags:\n        links:\n          github: https://github.com/jitsecurity-controls/jit-zap-fullscan-control\n          security_tool: https://www.zaproxy.org/docs/docker/full-scan/\n        security_tool: Zap\n      uses: 899025839375.dkr.ecr.us-east-1.amazonaws.com/zap:latest\n      with:\n        args: '--scan_mode web --authentication_mode ${{ context.asset.authentication_mode\n          }} --target_url ${{ context.asset.target_url }} --exclude_paths ${{ context.asset.exclude_paths\n          }} --api_domain ${{ context.asset.api_domain }} --login_url ${{ context.asset.login_page_url\n          }} --username ${{ context.asset.username }} --username_selector ${{ context.asset.username_css_selector\n          }} --password_selector ${{ context.asset.password_css_selector }} --rule_set_path\n          rule_sets/deployment-web.yml\n\n          '\n        env:\n          AUTHENTICATION_VALUE: ${{ jit_secrets.web_scan_authentication_value }}\n          JIT_CONFIG_CONTENT: ${{ context.config }}\n          PASSWORD: ${{ jit_secrets.web_scan_password }}\nname: Web App Security Deployment Workflow\ntrigger:\n  True:\n  - deployment\n",
                    "depends_on": [

                    ],
                    "params": None,
                    "plan_item_template_slug": None,
                    "asset_types": [
                        "web"
                    ],
                    "parsed_content": {
                        "name": "Web App Security Deployment Workflow",
                        "jobs": {
                            "web-security-detection": {
                                "asset_type": "web",
                                "default": True,
                                "runner": {
                                    "type": "jit",
                                    "setup": {
                                        "timeout_minutes": 10,
                                    }
                                },
                                "steps": [
                                    {
                                        "name": "Run ZAP",
                                        "with": {
                                            "args": "--scan_mode web --authentication_mode ${{ context.asset.authentication_mode }} --target_url ${{ context.asset.target_url }} --exclude_paths ${{ context.asset.exclude_paths }} --api_domain ${{ context.asset.api_domain }} --login_url ${{ context.asset.login_page_url }} --username ${{ context.asset.username }} --username_selector ${{ context.asset.username_css_selector }} --password_selector ${{ context.asset.password_css_selector }} --rule_set_path rule_sets/deployment-web.yml\n",
                                            "env": {
                                                "PASSWORD": "${{ jit_secrets.web_scan_password }}",
                                                "AUTHENTICATION_VALUE": "${{ jit_secrets.web_scan_authentication_value }}",
                                                "JIT_CONFIG_CONTENT": "${{ context.config }}"
                                            }
                                        },
                                        "uses": "899025839375.dkr.ecr.us-east-1.amazonaws.com/zap:latest",
                                        "tags": {
                                            "security_tool": "Zap",
                                            "links": {
                                                "security_tool": "https://www.zaproxy.org/docs/docker/full-scan/",
                                                "github": "https://github.com/jitsecurity-controls/jit-zap-fullscan-control"
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                        "trigger": {
                            "True": [
                                "deployment"
                            ]
                        }
                    }
                }
            ]
        }
    },
    "depends_on": {
        "workflow-enrichment-code": {
            "slug": "workflow-enrichment-code",
            "name": "Code Enrichment Workflow",
            "type": "workflow",
            "default": None,
            "content": "jobs:\n  enrich:\n    asset_type: repo\n    default: True\n    runner: github_actions\n    steps:\n    - name: Run code enrichment\n      uses: ghcr.io/jitsecurity-controls/control-enrichment-slim:latest\n      with:\n        args: --path \\${WORK_DIR:-.}\nname: Code Enrichment Workflow\n",
            "depends_on": [

            ],
            "params": None,
            "plan_item_template_slug": None,
            "asset_types": [
                "repo"
            ],
            "parsed_content": {
                "name": "Code Enrichment Workflow",
                "jobs": {
                    "enrich": {
                        "asset_type": "repo",
                        "default": True,
                        "runner": "github_actions",
                        "steps": [
                            {
                                "name": "Run code enrichment",
                                "with": {
                                    "args": "--path \\${WORK_DIR:-.}"
                                },
                                "uses": "ghcr.io/jitsecurity-controls/control-enrichment-slim:latest"
                            }
                        ]
                    }
                }
            }
        }
    }
}
