# Statement of Work — Loan Origination Platform on AWS

## 1. Objectives and business outcome
NorthBank will replace its on-premises loan origination system with an AWS-hosted
platform. Success is defined as: application-to-decision time reduced from 6 days
to under 24 hours, capacity for 50,000 applications per month, and a documented
audit trail satisfying the bank's internal controls review.

## 2. In-scope deliverables
1. **Architecture design document** — target-state design covering CloudFront,
   Application Load Balancer, ECS Fargate, Amazon RDS for PostgreSQL (Multi-AZ),
   Amazon S3 and AWS KMS, in ap-south-1.
2. **Landing zone** — AWS Control Tower with three accounts (dev, staging, prod),
   SCPs and centralised CloudTrail.
3. **Infrastructure as code** — Terraform modules for all deliverable-1 services,
   with a documented module interface.
4. **CI/CD pipeline** — build, test and deploy pipeline with automated rollback.
5. **Migration runbook** — step-by-step cutover procedure including rollback.
6. **Operational handover pack** — runbooks, dashboards and alert definitions.

## 3. Out of scope
The following are explicitly excluded and will be quoted separately if required:
- Application code changes to the existing loan origination application.
- Data migration from the legacy Oracle database.
- End-user training beyond the two handover sessions in deliverable 6.
- Production support after the 30-day hypercare period.
- Third-party software licences, including Oracle and any ISV tooling.
- Penetration testing and formal security certification.

## 4. Acceptance criteria
| Deliverable | Acceptance criteria |
|---|---|
| 1 | Design reviewed and signed off by NorthBank Chief Architect. |
| 2 | Three accounts provisioned; SCPs verified by NorthBank Security. |
| 3 | `terraform plan` produces zero diff against deployed state. |
| 4 | Pipeline deploys a change to staging and rolls it back automatically. |
| 5 | Runbook executed end-to-end in a rehearsal with under 4 hours downtime. |
| 6 | Two handover sessions delivered; NorthBank ops confirm dashboards. |

## 5. Assumptions and dependencies
- NorthBank provides AWS account access and an IAM role by week 1, day 3.
- NorthBank nominates a technical decision-maker available for weekly reviews.
- Network connectivity from on-premises is in place by week 4.
- Any dependency slipping beyond 5 working days triggers a change request and a
  corresponding timeline adjustment at the rates in section 7.

## 6. Timeline, phases and milestones
| Phase | Weeks | Exit criteria |
|---|---|---|
| Discovery | 1–2 | Assessment report accepted |
| Design | 3–5 | Deliverable 1 signed off |
| Build | 6–10 | Deliverables 2–4 deployed to staging |
| Cutover | 11 | Deliverable 5 rehearsed successfully |
| Hypercare | 12 | Deliverable 6 accepted |

## 7. Commercials and change control
Fixed price of INR 92,00,000 exclusive of taxes and AWS consumption charges,
invoiced 30% on signature and the balance on milestone acceptance. Any change to
scope requires a written change request; ContosoTech will provide an impact
estimate within 3 working days, and no work proceeds until signed by both parties.

## 8. Roles and responsibilities
| Workstream | ContosoTech | NorthBank |
|---|---|---|
| Architecture | Accountable | Consulted |
| Landing zone | Responsible | Approves SCPs |
| IaC and CI/CD | Responsible | Reviews |
| Cutover | Responsible | Accountable for go/no-go |
| Security review | Consulted | Accountable |
