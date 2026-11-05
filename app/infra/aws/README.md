# AWS Deployment Profile

Terraform for running the platform on Amazon EKS. The self-hosted Helm and Compose profiles stay the default, and this profile is an addition to them.

**Status: not verified on AWS.** This code has not been applied to an AWS account yet. Pricing is an estimate.

## Layers

| Layer | Contains | Lifetime |
| ----- | -------- | -------- |
| [`foundation/`](foundation/) | S3 buckets (Terraform state, data, observability, backups), ECR repositories, Vault unseal KMS key | Kept between tests |
| [`cluster/`](cluster/) | VPC, NAT gateway, EKS, node groups, IAM roles | Destroyed after each test |

Splitting the layers keeps files, backups and images when the expensive resources are deleted.

Pods get AWS access through IAM roles for service accounts (IRSA), so no long-lived AWS keys are stored in the cluster.

## Prerequisites

- Terraform 1.10 or newer
- AWS CLI v2, signed in with `aws sso login`
- `kubectl` within one minor version of the cluster, which defaults to Kubernetes 1.36
- A budget alert in AWS Budgets

## Foundation: first run

This layer costs about $1 a month for the KMS key, plus storage for what you keep in S3 and ECR. Run these commands from `foundation/`.

```bash
terraform init
terraform apply
```

Move its local state into S3. Copy `../backend.hcl.example` to `../backend.hcl`, and set the bucket to the `terraform_state_bucket` output. Then copy `backend.tf.example` to `backend.tf` and run:

```bash
terraform init -migrate-state -backend-config=../backend.hcl
```

## Cluster: create and destroy

**Charges start when you apply this layer.** Run these commands from `cluster/`, after copying `terraform.tfvars.example` to `terraform.tfvars` and setting your IP address.

```bash
terraform init -backend-config=../backend.hcl
terraform apply
```

Connect `kubectl` with the command from the `kubeconfig_command` output.

Remove anything that created AWS resources from inside Kubernetes before you destroy the layer. A load balancer left behind keeps charging and can block the delete.

```bash
helm uninstall kp -n kp
terraform destroy
```

Afterwards, check Load Balancers, Volumes, NAT gateways and Billing in the AWS console.

## Estimated cost (`eu-north-1`)

| Usage | Monthly estimate |
| ----- | ---------------- |
| Always on | ~$430 |
| 40 hours, then destroyed | ~$25 |

Set `ollama_node_count = 0` to save about $0.20 an hour while testing with the MOCK LLM.

Confirm prices in the [AWS Pricing Calculator](https://calculator.aws/). EKS costs six times more per hour once a Kubernetes version leaves standard support, so upgrade before that date.

## Lab trade-offs

| Choice | Reason | Production alternative |
| ------ | ------ | ---------------------- |
| One NAT gateway | Saves about $35 a month | One per availability zone |
| SSE-S3 and AES256 instead of customer KMS keys | No per-key fee | Customer-managed keys |
| No S3 access logs, replication or VPC flow logs | Lower cost for one user | Enable all three |
| Databases in the cluster on EBS | Keeps the design portable to the air-gapped profile | RDS and other managed stores |
| Kubernetes API reachable from one listed IP | Simple laptop access | Private access through a VPN |

Foundation buckets and the KMS key use `prevent_destroy`. To remove them, delete that flag on purpose and empty the buckets first.

## Vault

Vault runs inside EKS in the `vault` namespace, which matches the address already in the chart's `values.yaml`. This layer prepares its AWS access:

- **Auto-unseal:** the KMS key in `foundation/` unseals Vault after a restart, without manual unseal keys.
- **Snapshots:** the `vault_role_arn` role can write to `vault/` in the backups bucket.

Deleting the cluster deletes Vault's data disk, so take a Raft snapshot first. A restore needs that snapshot and the same KMS key. Keep the recovery keys and root token in a password manager, never in this repository.

## Not included yet

| Item | Phase |
| ---- | ----- |
| `gp3` storage class, load balancer controller, `values-aws.yaml` | 2 |
| Chart service accounts and S3 sign-in through IRSA | 3 |
| Ollama in the chart | 4 |
| Monitoring on EKS | 5 |
| Vault server and External Secrets Operator on EKS | 6 |
| Keycloak on EKS | 7 |
| GitLab runner and its IAM role | 8 |
| Database backup role, Vault snapshots and rebuild scripts | 9 |
