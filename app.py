import gitlab
import yaml
from kubernetes import client, config
from jinja2 import Template
import os

gitlab_api_url = os.environ["GITLAB_API_URL"]
gitlab_token = os.environ["GITLAB_PERSONAL_ACCESS_TOKEN"]
gitlab_group = os.environ["RESIDENCIES_PARENT_REPOSITORIES_ID"]

application_template = Template("""apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: "omp-{{ RESOURCE_ID }}"
spec:
  destination:
    namespace: "anarchy-operator"
    server: 'https://kubernetes.default.svc'
  source:
    path: "objects/ocp-init"
    repoURL: >-
      {{ REPO_URL }}
    targetRevision: HEAD
  project: default""")

repository_config_template = Template("""- name: omp-{{ RESOURCE_ID }}
  sshPrivateKeySecret:
    key: sshPrivateKey
    name: {{ SSH_SECRET_NAME }}
  type: git
  url: {{ REPO_URL }}
""")


def main() -> None:
    g = gitlab.Gitlab(gitlab_api_url, private_token=gitlab_token)
    config.load_incluster_config()
    custom_object_api = client.CustomObjectsApi()
    config_map_api = client.CoreV1Api()

    current_applications_list = custom_object_api.list_namespaced_custom_object(
        group="argoproj.io",
        version="v1alpha1",
        namespace="argo-cd",
        plural="applications",
    )
    current_application_names = list(map(lambda item: item["metadata"]["name"], current_applications_list["items"]))
    print(f"Current applications: {current_application_names}")

    g.auth()
    group = g.groups.get(gitlab_group)
    for project in group.projects.list(all=True, include_subgroups=True):
        # Iterate through relevant GitLab projects
        application = application_template.render(
            RESOURCE_ID=project.id,
            REPO_URL=project.ssh_url_to_repo,
        )
        application_data = yaml.load(application, Loader=yaml.FullLoader)
        print(f"Checking for {application_data['metadata']['name']}")

        # Check if we need to process this one or if it's already there
        if not application_data["metadata"]["name"] in current_application_names:
            # Create Application object in OpenShift
            print(f"Creating {application_data['metadata']['name']}")
            custom_object_api.create_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace="argo-cd",
                plural="applications",
                body=application_data,
            )

            # Edit ConfigMap to link the repo to an SSH secret
            config_map = config_map_api.read_namespaced_config_map(
                name="argocd-cm",
                namespace="argo-cd",
            )
            print(config_map.data)
            repository_config = repository_config_template.render(
                RESOURCE_ID=project.id,
                REPO_URL=project.ssh_url_to_repo,
                SSH_SECRET_NAME="stuff-for-now",
            )
            if "repositories" in config_map.data.keys():
                config_map.data['repositories'] += "\n" + repository_config
            else:
                config_map.data['repositories'] += repository_config
            config_map_api.patch_namespaced_config_map(name="argocd-cm", namespace="argo-cd", body=config_map)
        else:
            print(f"Found {application_data['metadata']['name']}, skipping")


main()
