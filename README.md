# Local Development

## Prerequisites
1. Docker
2. AWS Access
3. Pulumi Access (API key)
4. Git Repo Access (SSH key)

## Setup
1. Build the local development docker image
```
docker build . -t santorakubik-devops:latest
```
2. Run the local development docker container
```
docker run -v `pwd`:/src -it santorakubik-devops:latest bash
```
3. Initialize the local development container (from inside the container)
```
cd src
source .env
git remote set-url origin https://$GITHUB_USERNAME:$GITHUB_TOKEN`git remote get-url origin --push | sed 's/git@/@/g'`"
```
