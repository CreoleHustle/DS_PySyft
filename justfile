cluster_default := "k3d-syft-dev"
cluster_high := "k3d-syft-high"
cluster_low := "k3d-syft-low"
cluster_gw := "k3d-syft-gw"
cluster_signoz := "k3d-signoz"
ns_default := "syft"
ns_high := "high"
ns_low := "low"
ns_gw := "gw"

# ---------------------------------------------------------------------------------------------------------------------

port_default := "8080"
port_high := port_default
port_low := "8081"
port_gw := "8082"
port_signoz_ui := "3301"
port_signoz_otel := "4317"
port_registry := "5800"

registry_url := "k3d-registry.localhost:" + port_registry
signoz_otel_url := "http://host.k3d.internal:" + port_signoz_otel

# ---------------------------------------------------------------------------------------------------------------------

# devspace profiles (comma-separated)
profiles := ""

# enable tracing by adding "tracing" profile in devspace
tracing := "true"

_g_profiles := if tracing == "true" { profiles + ",tracing" } else { profiles }

# ---------------------------------------------------------------------------------------------------------------------

# this might break if you have alias python = python3 or either of the executable not pointing to the correct one
# just fix your system instead of making of fixing this
python_path := `which python || which python3`

# ---------------------------------------------------------------------------------------------------------------------

@default:
    just --list

# ---------------------------------------------------------------------------------------------------------------------

# Start a local registry on http://k3d-registry.localhost:{{port_registry}}
[group('registry')]
start-registry:
    k3d --version
    @-docker volume create k3d-registry-vol
    @-k3d registry create registry.localhost --port {{ port_registry }} -v k3d-registry-vol:/var/lib/registry --no-help

    if ! grep -q k3d-registry.localhost /etc/hosts; then \
        sudo {{ python_path }} scripts/patch_hosts.py --add-k3d-registry --fix-docker-hosts; \
    fi

    @curl --silent --retry 5 --retry-all-errors http://k3d-registry.localhost:{{ port_registry }}/v2/_catalog | jq
    @echo "\033[1;32mRegistring running at http://k3d-registry.localhost:{{ port_registry }}\033[0m"

[group('registry')]
delete-registry:
    -k3d registry delete registry.localhost
    -docker volume rm k3d-registry-vol

# ---------------------------------------------------------------------------------------------------------------------

# Launch a Datasite high-side cluster on http://localhost:{{port_high}}
[group('highside')]
start-high: (delete-cluster cluster_high) (create-cluster cluster_high port_high)

# Stop the Datasite high-side cluster
[group('highside')]
delete-high: (delete-cluster cluster_high)

[group('highside')]
deploy-high: (deploy-devspace cluster_high ns_default)

[group('highside')]
reset-high: (reset-syft cluster_high ns_default)

# Remove devpsace deployment + namespace from the high-side cluster
[group('highside')]
cleanup-high: (purge-devspace cluster_high ns_default) (delete-ns cluster_high ns_default)

# ---------------------------------------------------------------------------------------------------------------------

# Launch a Datasite low-side cluster on http://localhost:{{port_low}}
[group('lowside')]
start-low: (create-cluster cluster_low port_low)

# Stop the Datasite low-side cluster
[group('lowside')]
delete-low: (delete-cluster cluster_low)

# Deploy Syft to the low-side cluster
[group('lowside')]
deploy-low: (deploy-devspace cluster_low ns_default "-p datasite-low")

# Reset Syft DB state in the low-side cluster
[group('lowside')]
reset-low: (reset-syft cluster_low ns_default)

# Remove devpsace deployment + namespace from the low-side cluster
[group('lowside')]
cleanup-low: (purge-devspace cluster_low ns_default) (delete-ns cluster_low ns_default)

# ---------------------------------------------------------------------------------------------------------------------

# Launch a Gateway cluster on http://localhost:{{port_gw}}
[group('gateway')]
start-gw: (create-cluster cluster_gw port_gw)

# Delete the Gateway cluster
[group('gateway')]
delete-gw: (delete-cluster cluster_gw)

# Deploy Syft to the gateway cluster
[group('gateway')]
deploy-gw: (deploy-devspace cluster_gw ns_default "-p gateway")

# Reset Syft DB state in the gateway cluster
[group('gateway')]
reset-gw: (reset-syft cluster_gw ns_default)

# Remove devpsace deployment + namespace from the gateway cluster
[group('gateway')]
cleanup-gw: (purge-devspace cluster_gw ns_default) (delete-ns cluster_gw ns_default)

# ---------------------------------------------------------------------------------------------------------------------

# TODO - multi-namespace -> unique k3d ports
# # Launch a multi-agent cluster on http://localhost:{{port_default}}
# [group('shared')]
# start-shared: (create-cluster cluster_default port_default "--agents 2")

# # Stop the multi-agent cluster
# [group('shared')]
# delete-shared: (delete-cluster cluster_default)

# [group('shared')]
# deploy-ns-high: (deploy-devspace cluster_default ns_high)

# [group('shared')]
# delete-ns-high: (delete-ns cluster_default ns_high)

# [group('shared')]
# deploy-ns-low: (deploy-devspace cluster_default ns_low "-p datasite-low")

# [group('shared')]
# delete-ns-low: (delete-ns cluster_default ns_low)

# [group('shared')]
# deploy-ns-gw: (deploy-devspace cluster_default ns_gw "-p gateway")

# [group('shared')]
# delete-ns-gw: (delete-ns cluster_default ns_gw)

# ---------------------------------------------------------------------------------------------------------------------

# Launch SigNoz on http://localhost:{{port_signoz_ui}}
[group('signoz')]
start-signoz: && apply-signoz setup-signoz
    k3d cluster create signoz \
        --port {{ port_signoz_ui }}:3301@loadbalancer \
        --port {{ port_signoz_otel }}:4317@loadbalancer \
        --k3s-arg "--disable=metrics-server@server:*"

    @printf "Started SigNoz\n\
        Dashboard: \033[1;36mhttp://localhost:{{ port_signoz_ui }}\033[0m\n\
        OTEL Endpoint: \033[1;36mhttp://localhost:{{ port_signoz_otel }}\033[0m\n"

[group('signoz')]
delete-collector:
    helm uninstall k8s-infra

# Stop SigNoz cluster
[group('signoz')]
delete-signoz: (delete-cluster cluster_signoz)

[group('signoz')]
[private]
apply-collector cluster:
    @echo "Installing SigNoz OTel Collector"
    helm install k8s-infra k8s-infra \
        --repo https://charts.signoz.io \
        --kube-context {{ cluster }} \
        --set global.deploymentEnvironment=local \
        --set clusterName={{ cluster }} \
        --set otelCollectorEndpoint={{ signoz_otel_url }} \
        --set otelInsecure=true \
        --set presets.otlpExporter.enabled=true \
        --set presets.loggingExporter.enabled=true

[group('signoz')]
[private]
apply-signoz:
    @echo "Installing SigNoz on the cluster"
    helm install signoz signoz \
        --repo https://charts.signoz.io \
        --kube-context {{ cluster_signoz }} \
        --namespace platform \
        --create-namespace \
        --version 0.52.0 \
        --set frontend.service.type=LoadBalancer \
        --set otelCollector.service.type=LoadBalancer \
        --set otelCollectorMetrics.service.type=LoadBalancer

[group('signoz')]
[private]
setup-signoz:
    @echo "Waiting for SigNoz frontend to be available..."
    @bash ./packages/grid/scripts/wait_for.sh service signoz-frontend \
        --namespace platform --context {{ cluster_signoz }} &> /dev/null

    @echo "Setting up SigNoz account"
    @curl --retry 5 --retry-all-errors -X POST \
        -H "Content-Type: application/json" \
        --data '{"email":"admin@localhost","name":"admin","orgName":"openmined","password":"password"}' \
        http://localhost:3301/api/v1/register

    @printf '\nSignoz is running on http://localhost:3301\n\
        Email: \033[1;36madmin@localhost\033[0m\n\
        Password: \033[1;36mpassword\033[0m\n'

# ---------------------------------------------------------------------------------------------------------------------

# List all clusters
[group('cluster')]
list-clusters:
    k3d cluster list

# Stop all clusters
[group('cluster')]
[confirm('Confirm delete all clusters?')]
delete-clusters:
    k3d cluster delete --all

[group('cluster')]
[private]
create-cluster cluster port *args='': start-registry && (apply-coredns cluster) (apply-collector cluster)
    #!/bin/bash
    set -euo pipefail

    # remove the k3d- prefix
    CLUSTER_NAME=$(echo "{{ cluster }}" | sed -e 's/k3d-//g')

    k3d cluster create $CLUSTER_NAME \
        --port {{ port }}:80@loadbalancer \
        --registry-use k3d-registry.localhost:5800 {{ args }}

[group('cluster')]
[private]
delete-cluster *args='':
    #!/bin/bash
    set -euo pipefail

    # remove the k3d- prefix
    ARGS=$(echo "{{ args }}" | sed -e 's/k3d-//g')
    k3d cluster delete $ARGS

[group('cluster')]
[private]
delete-ns context namespace:
    kubectl delete ns {{ namespace }} --force --grace-period=0 --context {{ context }}

[group('cluster')]
[private]
apply-coredns cluster:
    @echo "Applying custom CoreDNS config"

    kubectl apply -f ./scripts/k8s-coredns-custom.yml --context {{ cluster }}
    kubectl delete pod -n kube-system -l k8s-app=kube-dns --context {{ cluster }}

# ---------------------------------------------------------------------------------------------------------------------

[group('devspace')]
[private]
deploy-devspace cluster namespace *args='':
    #!/bin/bash
    set -euo pipefail

    cd packages/grid

    PROFILE="{{ _g_profiles }}"
    PROFILE=$(echo "$PROFILE" | sed -E 's/^,*|,*$//g')
    if [ -n "$PROFILE" ]; then
        PROFILE="-p $PROFILE"
    fi

    devspace deploy -b \
        --no-warn \
        --kube-context {{ cluster }} \
        --namespace {{ namespace }} \
        $PROFILE \
        {{ args }} \
        --var CONTAINER_REGISTRY={{ registry_url }}

[group('devspace')]
[private]
purge-devspace cluster namespace:
    #!/bin/bash
    set -euo pipefail

    cd packages/grid
    devspace purge --force-purge --kube-context {{ cluster }} --no-warn --namespace {{ namespace }}
    sleep 3

# ---------------------------------------------------------------------------------------------------------------------

[group('cloud')]
[private]
deploy-cloud cluster registry namespace profile:
    #!/bin/bash
    set -euo pipefail

    kubectl config get-contexts {{ cluster }} > /dev/null
    # cloud deployments always have tracing false + platform=amd64
    just tracing=false registry_url={{ registry }} \
        deploy-devspace {{ cluster }} {{ namespace }} "-p {{ profile }} --var PLATFORM=amd64"

[group('cloud')]
[private]
purge-cloud cluster namespace:
    #!/bin/bash
    set -euo pipefail

    kubectl config get-contexts {{ cluster }} > /dev/null
    just purge-devspace {{ cluster }} {{ namespace }}

# ---------------------------------------------------------------------------------------------------------------------

# Auth all components required for deploying Syft to Google Cloud
[group('cloud-gcp')]
auth-gcloud gcp_project gcp_region gcp_cluster gcp_registry:
    # get artifact registry registry
    gcloud auth configure-docker {{ gcp_registry }} --quiet
    # get cluster credentials
    gcloud container clusters get-credentials {{ gcp_cluster }} --region {{ gcp_region }} --project {{ gcp_project }}

# Deploy local code as datasite-high to Google Kubernetes Engine
[group('cloud-gcp')]
deploy-gcp-high gcp_cluster gcp_registry namespace="syft": (deploy-cloud gcp_cluster gcp_registry namespace "gcp")

# Deploy local code as datasite-high to Google Kubernetes Engine
[group('cloud-gcp')]
deploy-gcp-low gcp_cluster gcp_registry namespace="syft": (deploy-cloud gcp_cluster gcp_registry namespace "gcp-low")

# ---------------------------------------------------------------------------------------------------------------------

# Deploy local code as datasite-high to Azure Kubernetes Service
[group('cloud-az')]
deploy-az-high aks_cluster az_registry namespace="syft": (deploy-cloud aks_cluster az_registry namespace "azure")

# ---------------------------------------------------------------------------------------------------------------------

# Reset Syft state in a cluster
[group('utils')]
[private]
reset-syft name namespace:
    kubectl config use-context {{ name }}
    scripts/reset_k8s.sh

# K9s into the Datasite High cluster
[group('utils')]
k9s-high:
    k9s --context {{ cluster_high }}

# K9s into the Datesite Low cluster
[group('utils')]
k9s-low:
    k9s --context {{ cluster_low }}

# K9s into the Gateway cluster
[group('utils')]
k9s-gw:
    k9s --context {{ cluster_gw }}

# K9s into the Signoz cluster
[group('utils')]
k9s-signoz:
    k9s --context {{ cluster_signoz }}

# Stop all Syft clusters + registry
[group('utils')]
[confirm('Confirm delete all clusters, registry and volume?')]
delete-all: delete-clusters delete-registry
    @echo "Stopped all Syft components"
