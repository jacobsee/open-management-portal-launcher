import gitlab
import yaml
import time
from kubernetes import client, config
from jinja2 import Template
import os

gitlab_api_url = os.environ["GITLAB_API_URL"]
gitlab_token = os.environ["GITLAB_PERSONAL_ACCESS_TOKEN"]
gitlab_group = os.environ["RESIDENCIES_PARENT_REPOSITORIES_ID"]

application_template = Template("""apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: omp-{{ RESOURCE_ID }}
spec:
  destination:
    namespace: anarchy-operator
    server: 'https://kubernetes.default.svc'
  source:
    path: objects/ocp-init
    repoURL: >-
      {{ REPO_URL }}
    targetRevision: HEAD
  project: default""")


def main() -> None:
    g = gitlab.Gitlab(gitlab_api_url, private_token=gitlab_token)
    config.load_incluster_config()
    custom_object_api = client.CustomObjectsApi()

    g.auth()
    group = g.groups.get(gitlab_group)
    for project in group.projects.list(all=True, include_subgroups=True):
        application = application_template.render(RESOURCE_ID=project.id, REPO_URL=project.ssh_url_to_repo)
        application_data = yaml.safe_load(application)
        # print(project)
        # print(application + "\n\n")

        custom_object_api.create_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace="anarchy-operator",
            plural="Applications",
            body=application_data,
        )


def main2() -> None:
    print("I am happy running in this container!")
    while True:
        time.sleep(1)


main2()
