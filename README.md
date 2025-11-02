# eks-strands-autoscaler

> [Building Production-Grade Strands Agents on Amazon EKS with KEDA](https://aws.plainenglish.io/building-production-grade-strands-agents-on-amazon-eks-with-keda-triggerauthentication-irsa-0eac5c0e40d9)

Deploy a Strand Agent system to Amazon EKS that scales pods and jobs dynamically using KEDA.

---

#### Create, Update, and Confirm the EKS cluster (OIDC + IRSA ready)

```shell
eksctl create cluster \
  --name strand-agents-keda \
  --region us-east-1 \
  --with-oidc \
  --managed \
  --nodes 3 \
  --node-type t3.xlarge
```

```shell
eksctl utils associate-iam-oidc-provider \
  --region us-east-1 \
  --cluster strand-agents-keda \
  --approve
```

---

#### Install KEDA (Helm) and Metrics Pipeline

```shell
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm upgrade --install keda kedacore/keda \
  --namespace keda --create-namespace \
  --set metricsServer.enabled=true
```

```shell
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install kube-prom prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace
```

---

#### Build the Strand Agent services

- Build & push to ECR (replace <acct>, <region>, <repo>)

```shell
aws ecr create-repository --repository-name strand-agent
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <acct>.dkr.ecr.us-east-1.amazonaws.com
```

```shell
docker build -t strand-agent:latest .
docker tag strand-agent:latest <acct>.dkr.ecr.us-east-1.amazonaws.com/strand-agent:latest
docker push <acct>.dkr.ecr.us-east-1.amazonaws.com/strand-agent:latest
```

- AWS resources: SQS queue + DynamoDB table

```shell
aws sqs create-queue --queue-name strand-agent-jobs
aws dynamodb create-table \
  --table-name StrandAgentMemory \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

- IAM for IRSA (no static keys)

```shell
aws iam create-policy --policy-name StrandAgentsPolicy --policy-document file://iam-policy.json
```

- Create a ServiceAccount + IAM role (IRSA)

```shell
kubectl create namespace agents
eksctl create iamserviceaccount \
  --name strand-agents-sa \
  --namespace agents \
  --cluster strand-agents-keda \
  --attach-policy-arn arn:aws:iam::<acct>:policy/StrandAgentsPolicy \
  --approve \
  --override-existing-serviceaccounts
```

---

#### Configure Agents

- Kubernetes Manifests (Deployments, Services, PDB, NetworkPolicy)
- KEDA TriggerAuthentication (IRSA) + Multi-Trigger ScaledObject

---

#### Test

```shell
curl -X POST https://agents.example.com/query \
  -H "Content-Type: application/json" \
  -d '{"message":"Summarize the latest EKS autoscaling strategies"}'
```

---

#### Queue a background job

```shell
aws sqs send-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/<acct>/strand-agent-jobs \
  --message-body '{"prompt":"Batch-process 1k rows and write analysis to S3"}'
```

---

#### Watch KEDA scale

```shell
kubectl get hpa,scaledobject,scaledjob -A
kubectl get jobs -n agents
kubectl get pods -n agents -w
```

#### Configure Agents

```shell
kubectl apply -f agents/00-secret.yaml
kubectl apply -f agents/10-deploy-web.yaml
kubectl apply -f agents/15-pdb-np.yaml
kubectl apply -f agents/20-servicemonitor.yaml
kubectl apply -f agents/30-trigger-auth.yaml
kubectl apply -f agents/40-scaledobject-web.yaml
kubectl apply -f agents/50-job-worker.yaml
kubectl apply -f agents/60-scaledjob.yaml
kubectl apply -f agents/70-ingress.yaml
```