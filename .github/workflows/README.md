## Releases and environment promotion

Two workflows run on every push to `main` during the pipeline migration.
[Release pipeline - dev & test](release-pipeline.yml) uses the
[central release pipeline](https://github.com/cds-snc/canadalogin-release-pipeline)
with [this configuration](../release-pipeline-configuration.yml).
[Legacy release pipeline - staging & prod](release-pipeline-legacy.yml) keeps the
existing deployment path for the remaining environments.

| Environment | Workflow | Deployment selection |
| --- | --- | --- |
| Dev | Central | Every push's commit |
| Test | Central | `.deployed_versions/test.json`, deployed when changed by a release PR |
| Staging | Legacy | `.deployed_versions/staging.json`, updated by a promotion PR |
| Production | Legacy | `.deployed_versions/prod.json`, updated by a promotion PR |

The central workflow is the only backend-image publisher and Release Please
runner. It builds dev/test frontends at `<environment>/<sha>/` in each artifact
bucket and publishes backend SHA tags in dev for cross-account ECR replication.
The legacy workflow still builds staging/prod frontends at `<sha>/`, deploys their
pinned versions, and publishes the staging-pinned load-test image as `latest`.
It verifies the selected backend image exists in the destination account before
deployment; it does not rebuild backend images. Keep existing legacy Variables,
Secrets and artifact prefixes while either environment remains on that workflow.

To promote an existing release, open a PR that changes only the relevant
deployment version file, using a title such as
`ci(deploy): promote 1.12.21 to staging`. After the required review and merge,
Actions deploys that selected release. Check the environment's frontend and
backend deployment jobs for the resolved release SHA and successful completion.
A backend job may confirm that the selected image is already deployed.

Release Please ignores commits that only change files in `.deployed_versions/`.
This prevents promoting an existing release from generating another release PR.
Commits that also change application code, dependencies, workflows or other files
remain eligible under the existing commit-type rules, including bot
`chore(deps)` updates. Release Please still updates the test version when its
release PR is merged. Keep promotion changes separate from other changes.

The pinned Release Please version matches excluded directory prefixes, so use
`.deployed_versions` rather than individual filenames or globs. Its exclusion
filter also skips empty commits; do not use an empty `Release-As` commit to force
a version bump while this filter is configured.

## Dev/test handover and manual deployments

Merging the pipeline change without changing version files centrally deploys dev
only. Before manually handing over test, copy and verify its exact existing
frontend artifact from `<pinned-sha>/` to `test/<pinned-sha>/` in the test artifact
bucket. Do not rebuild a pinned release to substitute for the original artifact.
Verify the backend image is present in test, then dispatch
`Release pipeline - dev & test` from current `main`, selecting `test` with
`rebuild` and `disable_old_code_protection` left false. Check authentication,
frontend assets, ECS stability, SSM image tracking and Terraform drift.

The central workflow's manual selector offers only dev and test, and always
passes `force-redeploy: false`. Manual deployments without rebuilding require
the selected version's existing artifacts. The legacy workflow's manual dispatch
continues to process both staging and prod at their current pins. Neither
workflow can deploy an environment owned by the other. Version pins and their
CODEOWNER review requirements are unchanged; manual dispatch does not obtain a
new version-file approval.

Drain old deployment runs before merging the handover. The two workflows have
separate deployment locks because their environment ownership is disjoint.
They run independently, so a central failure does not block legacy deployments.
Before promoting a newly built release to staging/prod, confirm its central build
succeeded, ECR replication completed, and the legacy frontend artifact exists.

For the next environment migration, add it to the central configuration and
manual selector, and remove it from all legacy build/deploy matrices and
deployment notifications in the same PR. Transfer load-test publication to
central when staging migrates, not before.

To return dev/test to legacy, drain central runs and use a reviewed change on
current `main` that restores their legacy deployment scope and a single
immutable-aware backend publisher. Retain current version pins, verify legacy
frontend artifacts, and account for central digest image references when
checking ECS/SSM. Do not rerun an old workflow SHA or make ECR tags mutable.

## Setup ACT to run Github Actions Locally

### Overview
Act is a tool to execute GitHub Actions workflows locally. Use Act to build your infrastrucutre and to setup swagger for your scratch account.

### Installation Instructions:
- Repo: https://github.com/nektos/act?tab=readme-ov-file
- Homebrew Installation: https://nektosact.com/installation/homebrew.html

### Configuration File
Create a `.actrc` file in your root folder that has the following contents

```
# Set the default platform for runners
-P ubuntu-latest=ghcr.io/catthehacker/ubuntu:act-latest
--container-daemon-socket -
# Pass environment variables directly
--env AWS_ACCESS_KEY_ID=
--env AWS_SECRET_ACCESS_KEY=
--env AWS_SESSION_TOKEN=
--env AWS_REGION=ca-central-1
```

Check that your workflow is specifing your local working branch and not the `main` branch

```
on:
  push:
    branches:
      - YOUR-LOCAL-BRANCH-HERE
```

### AWS CLI
Act is a lightweight simulated runner. If your workflow requires the AWS CLI for tasks like interacting with S3, you need to include the following step in your GitHub Actions workflow:

```
- name: Install AWS CLI
  run: |
    sudo apt-get update
    sudo apt-get install -y awscli
```

### Add Secrets to your workflow
The simulated runner wont be able to use the `aws credentials using OIDC role`. Temporarily replace the OIDC step with the follwing in the workflow you are testing.

```
 - name: AWS Credentials
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_SESSION_TOKEN: ${{ secrets.AWS_SESSION_TOKEN }}
          AWS_REGION: ${{ secrets.AWS_REGION }}
          FRONTEND_APP_S3_BUCKET: ${{ secrets.FRONTEND_APP_S3_BUCKET }}
        run: |
          echo "AWS credentials are set for locally testing the github action."
```



Full example of implementing the aws cli and credentials

```
     - name: Install AWS CLI
        run: |
            sudo apt-get update
            sudo apt-get install -y awscli

      - name: AWS Credentials
        env:
            AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
            AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
            AWS_SESSION_TOKEN: ${{ secrets.AWS_SESSION_TOKEN }}
            AWS_REGION: ${{ secrets.AWS_REGION }}
            FRONTEND_APP_S3_BUCKET: ${{ secrets.FRONTEND_APP_S3_BUCKET }}
        run: |
            echo "AWS credentials are set for locally testing the github action."

```

## Debug Docker daemon 
https://github.com/nektos/act/issues/1051
https://github.com/nektos/act/issues/2239
