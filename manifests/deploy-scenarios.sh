#!/bin/bash

# exit on error
set -e

# Target namespace
NAMESPACE="k8s-ai-demo-tests"

# Resolve absolute path to the directory this script is located in
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check action
ACTION="${1:-deploy}"

if [ "$ACTION" = "clean" ] || [ "$ACTION" = "delete" ]; then
    echo "============================================="
    echo "  Cleaning Up Failure Scenarios...           "
    echo "============================================="
    kubectl delete namespace $NAMESPACE --ignore-not-found=true
    echo "Clean up completed successfully."
    exit 0
fi

echo "============================================="
echo "  Deploying Kubernetes Failure Scenarios     "
echo "============================================="

# Create namespace if it doesn't exist
echo "1. Creating namespace: $NAMESPACE..."
kubectl create namespace $NAMESPACE 2>/dev/null || echo "Namespace '$NAMESPACE' already exists."

# Deploy scenarios
echo "2. Applying scenario manifests from $DIR..."
kubectl apply -f "$DIR/scenario1-crashloop.yaml"
kubectl apply -f "$DIR/scenario2-imagepull.yaml"
kubectl apply -f "$DIR/scenario3-oomkilled.yaml"
kubectl apply -f "$DIR/scenario4-selector-mismatch.yaml"

echo ""
echo "============================================="
echo "  Failure Scenarios Deployed Successfully    "
echo "============================================="
echo "Verify status in another terminal: kubectl get pods -n $NAMESPACE"
echo "Select your target cluster context on the dashboard cockpit to investigate."
echo ""
echo "To clean up after testing, run:"
echo "  $0 clean"
echo "============================================="
