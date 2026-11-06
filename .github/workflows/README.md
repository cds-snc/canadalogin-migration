## Releases and environment promotion

The release pipeline runs on every push to `main`. Each environment selects its
deployment separately:

| Environment | Deployment selection |
| --- | --- |
| Dev | The commit that triggered the pipeline |
| Test | `.deployed_versions/test.json`, updated by the Release Please release PR |
| Staging | `.deployed_versions/staging.json`, updated by a promotion PR |
| Production | `.deployed_versions/prod.json`, updated by a promotion PR |

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
